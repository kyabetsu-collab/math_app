# ==============================
# 数学学習アプリ【完全完成版】
# ==============================

import streamlit as st
import json, random, os, re, math
import pandas as pd
import sympy as sp
from datetime import datetime

# ==============================
# 設定
# ==============================
PROBLEM_FILE = "problems.json"
RESULT_FILE = "results.csv"
TEACHER_PASSWORD = "20020711"

# ==============================
# 共通
# ==============================
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def load_problems():
    if os.path.exists(PROBLEM_FILE):
        with open(PROBLEM_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_problems(problems):
    with open(PROBLEM_FILE, "w", encoding="utf-8") as f:
        json.dump(problems, f, ensure_ascii=False, indent=2)

# ==============================
# 採点
# ==============================
def normalize(s):
    if not isinstance(s, str):
        return s
    s = s.replace("　", " ").strip()
    s = re.sub(r"\s+", "", s)
    return s

def is_equal(student, correct):
    try:
        return sp.simplify(sp.sympify(student) - sp.sympify(correct)) == 0
    except:
        try:
            return abs(float(student) - float(correct)) < 1e-6
        except:
            return normalize(student) == normalize(correct)

def check_answer(student, correct):
    if isinstance(correct, list):
        return any(is_equal(student, c) for c in correct)
    return is_equal(student, correct)

# ==============================
# 生徒画面
# ==============================
def student_view():
    st.header("✏ 生徒用テスト")
    sid = st.text_input("生徒_


