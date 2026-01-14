# backEnd/guardrails.py
import re
import io
# import json
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple

try:
    import pdfplumber
except Exception:
    pdfplumber = None

try:
    import pytesseract
    from PIL import Image
except Exception:
    pytesseract = None
    Image = None


# ====== 可調參數（先用這組就好） ======
OCR_CONF_THRESHOLD = 0.85     # OCR 平均置信度門檻
RETRIEVAL_SIM_THRESHOLD = 0.75  # 向量檢索門檻（不足就拒答）
FIELD_CONF_THRESHOLD = 0.75     # 欄位輸出置信度門檻（不足就拒答）

# 基本規則（可換成外部 rules.json）
RULES = {
    "min_total_hours": 12,
    "date_regex": r"(20\d{2})[./-](0?[1-9]|1[0-2])[./-](0?[1-9]|[12]\d|3[01])",
    "hours_regex": r"\b(\d{1,3})\s*(小時|hr|hrs|hours?)\b",
}


@dataclass
class PreflightResult:
    ok: bool
    text: str
    meta: Dict[str, Any]
    reason: Optional[str] = None


def _avg_tesseract_conf(ocr_data: str) -> float:
    """
    從 tesseract TSV 內容估平均 conf（-1 為無字元的行要排除）
    """
    lines = ocr_data.splitlines()[1:]  # 跳 header
    confs = []
    for ln in lines:
        parts = ln.split('\t')
        if len(parts) >= 12:
            try:
                c = float(parts[10])
                if c >= 0:
                    confs.append(c)
            except Exception:
                pass
    return (sum(confs) / len(confs) / 100.0) if confs else 0.0


def preflight_from_upload(storage) -> PreflightResult:
    """
    上游保險絲：將上傳檔轉文字，並回報 OCR/解析品質。
    - 優先 pdfplumber（可抽出向量文字）
    - 不行或疑似掃描，再走 Tesseract（若可用）
    """
    data = storage.read()
    name = (storage.filename or '').lower()
    mime = storage.mimetype or ''
    is_pdf = name.endswith('.pdf') or mime.startswith('application/pdf') or data[:4] == b'%PDF'

    meta = {"is_pdf": is_pdf, "engine": None, "ocr_confidence": None}

    # 1) 試 pdfplumber
    if is_pdf and pdfplumber:
        try:
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                texts = []
                for p in pdf.pages[:5]:  # 取前 5 頁夠用了，避免超慢
                    txt = p.extract_text() or ""
                    texts.append(txt)
                text = "\n".join(texts).strip()
                # 若幾乎沒有向量文字，可能是掃描件
                if len(text) >= 50:
                    meta["engine"] = "pdfplumber"
                    return PreflightResult(ok=True, text=text, meta=meta)
        except Exception:
            pass

    # 2) 掃描件走 Tesseract
    if pytesseract and Image:
        try:
            # 嘗試將整份當成單張影像（簡化版最小可用）
            img = Image.open(io.BytesIO(data))
            ocr_text = pytesseract.image_to_string(img, lang="chi_tra+eng")
            tsv = pytesseract.image_to_data(img, lang="chi_tra+eng", output_type='string')
            conf = _avg_tesseract_conf(tsv)
            meta.update({"engine": "tesseract", "ocr_confidence": conf})
            if conf < OCR_CONF_THRESHOLD:
                return PreflightResult(ok=False, text=ocr_text, meta=meta,
                                       reason=f"OCR 置信度過低 {conf:.2f} < {OCR_CONF_THRESHOLD}")
            return PreflightResult(ok=True, text=ocr_text, meta=meta)
        except Exception:
            pass

    return PreflightResult(ok=False, text="", meta=meta, reason="無法解析檔案（缺少 pdfplumber 或 Tesseract）")


# ====== 下游守門：欄位與總體規則 ======
def regex_like_date(s: str) -> bool:
    return re.search(RULES["date_regex"], s) is not None


def regex_like_hours(s: str) -> Tuple[bool, Optional[int]]:
    m = re.search(RULES["hours_regex"], s, flags=re.IGNORECASE)
    if not m:
        return False, None
    try:
        return True, int(m.group(1))
    except Exception:
        return True, None


def post_validate(pred: Dict[str, Any]) -> Dict[str, Any]:
    """
    將模型輸出的欄位逐一檢查（欄位置信度＆正則），不符門檻就強制 abstain。
    期望輸入 pred["fields"][field] = {value, confidence, evidence, abstain}
    """
    fields = pred.get("fields", {})
    patched = False

    # 欄位級門檻
    for k, v in fields.items():
        conf = float(v.get("confidence", 0.0) or 0.0)
        if conf < FIELD_CONF_THRESHOLD:
            v["abstain"] = True
            patched = True

    # 正則檢查（舉例：日期、時數）
    if "date_start" in fields and fields["date_start"].get("value"):
        if not regex_like_date(str(fields["date_start"]["value"])):
            fields["date_start"]["abstain"] = True
            patched = True

    if "date_end" in fields and fields["date_end"].get("value"):
        if not regex_like_date(str(fields["date_end"]["value"])):
            fields["date_end"]["abstain"] = True
            patched = True

    if "hours" in fields and fields["hours"].get("value") is not None:
        ok, hv = regex_like_hours(str(fields["hours"]["value"]))
        if not ok and not isinstance(fields["hours"]["value"], (int, float)):
            fields["hours"]["abstain"] = True
            patched = True

    pred["_patched_by_guardrails"] = patched
    return pred


def overall_business_rules(pred: Dict[str, Any]) -> Dict[str, Any]:
    """
    總體規則（例如：總時數 >= 12；若缺關鍵欄位則不得自動通過）
    在響應上加上 overall_pass 與 reasons
    """
    fields = pred.get("fields", {})
    reasons = []

    # 關鍵欄位都不能 abstain
    key_fields = ["course_name", "hours", "date_start"]
    for f in key_fields:
        fv = fields.get(f, {})
        if fv.get("abstain") or fv.get("value") in (None, "", []):
            reasons.append(f"關鍵欄位缺失或不確定：{f}")

    # 時數下限
    hours_v = fields.get("hours", {}).get("value")
    try:
        hours_num = int(hours_v)
    except Exception:
        ok, hv = regex_like_hours(str(hours_v))
        hours_num = hv if ok else None

    if hours_num is None:
        reasons.append("無法解析時數")
    elif hours_num < RULES["min_total_hours"]:
        reasons.append(f"總時數不足（{hours_num} < {RULES['min_total_hours']}）")

    overall_pass = len(reasons) == 0
    pred["overall_pass"] = overall_pass
    pred["overall_reasons"] = reasons
    return pred
