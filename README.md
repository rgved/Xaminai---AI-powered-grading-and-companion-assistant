---
title: Xaminai – AI Grading & Companion Model
emoji: 📝
colorFrom: blue
colorTo: green
sdk: streamlit
sdk_version: "1.37.0"
app_file: app.py
pinned: false
---

# 📝 Xaminai – AI Grading & Companion Model

## 📌 Project Overview
Xaminai is an **AI-powered grading and companion assistant** built for the  
**OpenAI Academy x NxtWave Buildathon 2025**.  

It automates exam evaluation while also helping students frame better answers.  
With multiple grading modes and a companion mode, it’s designed to support both **examiners** and **students**.

---

## 🚀 Features
- **Grading Modes:** Easy, Medium, Tough  
- **Companion Mode:** Provides feedback, improvement steps, and keywords for learning  
- **Input Options:** Text, PDF, DOCX/DOC (from device or Google Drive)  
- **Custom Evaluation:** Enter correct answers and set max score per question  
- **Detailed Results:** Feedback table with Score, Justification, and Improvement Suggestions  
- **Download Options:** Export evaluated results as PDF or DOC  

---

## ⚙️ Tech Stack
- **LLM:** Microsoft Phi-3.5 Mini Instruct  
- **Framework:** Streamlit  
- **Deployment:** Hugging Face Spaces (Hybrid: trained/tested on Colab, deployed here)  
- **Integrations:** Google Drive (for file input)  

---

## ⚠️ Important Notice

👉 **Grading might take longer than expected** on Hugging Face Spaces.  
This is because the Space runs **only on CPU** (no GPU support), and evaluation involves LLM inference, which is computationally heavy.  

If you want **faster performance**, try running the project locally with a GPU or use Google Colab.  

---

## 📊 Architecture / Workflow
