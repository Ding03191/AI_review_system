# Prompt Refine

## Goal

### Abstract

This is an feedback and scoring system using AI models, based on Double Prompt concept.
![image](https://github.com/user-attachments/assets/1567b6bc-12c0-4c19-bfaa-8c32033bf112)

## Developing history

### 20250312

- Created the repository and ready to construct the project.

### 20250314 Happy Valentine :P

- Added backEnd and frontEnd folder.
  - backEnd folder: Includes app.py and promptList with prompt.txt.
  - frontEnd folder: Includes index.html.
- The prompt example is just a demonstration of how to tell AI to give scores and feedback.
- For app.py the prompts can be modified and added into the system.
  - When changing the contents and the parameters in app.py, rememeber to add the same parameters in index.html.
- If wanna test out, please run app.py at first, then run index.html. (Both are local host, if wanna host with fixed IP need other stuffs.)
  - app.py's Environment API key requires openAI's API key to be set in the Environment. Thus, can not just execute then run.
  - Try run `$env:OPENAI_API_KEY = "your API key"` in your powershell, and you can use `echo $env:OPENAI_API_KEY` to check if the key is set.

### 20250402 (SSBhbSBzbyBmcmVha2luZyBzY3Jld2VkIGJ5IHNvbWVvbmUgSSB1c2VkIHRvIHRydXN0Lg==) 這串不是API KEY喔 不要用

- Construct the brief structure of the project.
- The project have to read PDF.
- The scoring history should be added into DB (currently using SQLite)
  - Data row: applicantStdn, applicantNo, applicantName, isPassed, aiFeedback, applyDate, applyTime
- dataAnalyze.py:
  - 處理PDF資料轉換為字串給AI讀，然後回傳json格式
- dbStoring.py:
  - 處理獲得的json並儲存到DB內。
- functions.py:
  - 一些基本函式
- tokenUsed.txt:
  - 紀錄目前的token總消耗
  