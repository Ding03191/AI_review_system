const API_BASE = "http://127.0.0.1:5000";
let currentTask = null;

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("btnLoad").addEventListener("click", loadNext);
  document.getElementById("btnSave").addEventListener("click", submitLabel);

  // 進頁面就先載一筆
  loadNext();
});

async function loadNext() {
  try {
    const res = await fetch(`${API_BASE}/api/label/next`);
    const data = await res.json();

    if (data.message === "no_pending_task") {
      currentTask = null;
      alert("目前沒有待標記資料。");
      fillEmpty();
      return;
    }

    currentTask = data;
    renderTask(data);
  } catch (err) {
    console.error(err);
    alert("載入資料失敗，請檢查後端是否有啟動。");
  }
}

function fillEmpty() {
  document.getElementById("applicantStdn").textContent = "-";
  document.getElementById("applicantName").textContent = "-";
  document.getElementById("applicantNo").textContent = "-";
  document.getElementById("applyDateTime").textContent = "-";

  const aiIsPassedEl = document.getElementById("aiIsPassed");
  aiIsPassedEl.textContent = "尚未載入";
  aiIsPassedEl.className = "pill";

  document.getElementById("aiFeedback").textContent = "(無資料)";
}

function renderTask(task) {
  document.getElementById("applicantStdn").textContent = task.applicantStdn;
  document.getElementById("applicantName").textContent = task.applicantName;
  document.getElementById("applicantNo").textContent = task.applicantNo;
  document.getElementById("applyDateTime").textContent =
    `${task.applyDate} ${task.applyTime}`;

  const aiIsPassedEl = document.getElementById("aiIsPassed");
  const isPassed = task.aiResult && task.aiResult.isPassed;

  aiIsPassedEl.textContent = isPassed ? "通過" : "未通過";
  aiIsPassedEl.className = "pill " + (isPassed ? "ok" : "ng");

  document.getElementById("aiFeedback").textContent =
    task.aiResult && task.aiResult.aiFeedback
      ? task.aiResult.aiFeedback
      : "(AI 沒有回傳意見)";

  // 清空標記欄位
  document.getElementById("labelIsCorrect").checked = false;
  document.getElementById("correctedIsPassed").value = "";
  document.getElementById("correctedFeedback").value = "";
  document.getElementById("reviewComment").value = "";
}

async function submitLabel() {
  if (!currentTask) {
    alert("目前沒有載入任何案件。請先點「載入下一筆」。");
    return;
  }

  const labelIsCorrect = document.getElementById("labelIsCorrect").checked;
  const correctedIsPassedVal =
    document.getElementById("correctedIsPassed").value;
  const correctedFeedback =
    document.getElementById("correctedFeedback").value.trim();
  const reviewComment =
    document.getElementById("reviewComment").value.trim();

  let correctedIsPassed = null;
  if (correctedIsPassedVal === "true") correctedIsPassed = true;
  if (correctedIsPassedVal === "false") correctedIsPassed = false;

  const payload = {
    applicantStdn: currentTask.applicantStdn,
    applicantNo: currentTask.applicantNo,
    labelIsCorrect,
    correctedIsPassed,
    correctedFeedback: correctedFeedback || null,
    reviewer: "teacher", // 之後可改成登入帳號
    reviewComment,
  };

  try {
    const res = await fetch(`${API_BASE}/api/label/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (data.status === "ok") {
      alert("標記已儲存！");
      loadNext();
    } else {
      console.error(data);
      alert("儲存失敗，請看 console。");
    }
  } catch (err) {
    console.error(err);
    alert("送出失敗，請檢查後端是否有啟動。");
  }
}
