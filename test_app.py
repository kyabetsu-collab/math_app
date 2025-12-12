import streamlit as st
import random
import pandas as pd
import json
import math
import sympy as sp
import re

# ================================
# JSON保存・読み込み
# ================================
PROBLEM_FILE = "problems.json"

def save_problems():
    with open(PROBLEM_FILE, "w", encoding="utf-8") as f:
        json.dump(st.session_state.all_problems, f, ensure_ascii=False, indent=2)

def load_problems():
    try:
        with open(PROBLEM_FILE, "r", encoding="utf-8") as f:
            st.session_state.all_problems = json.load(f)
    except FileNotFoundError:
        st.session_state.all_problems = []
        save_problems()

# ================================
# 数式・複数回答評価
# ================================
def safe_eval(expr):
    try:
        expr = expr.replace("√", "sqrt")
        val = eval(expr, {"sqrt": math.sqrt})
        if isinstance(val, (int, float)):
            return val
        return None
    except:
        return None

def normalize_answer(ans):
    """空白除去・全角→半角・カンマ区切りのトリム"""
    if not isinstance(ans, str):
        return ans
    ans = ans.replace("　", " ")  # 全角スペースを半角に
    ans = ans.strip()
    ans = re.sub(r"\s*,\s*", ",", ans)
    return ans

def _is_equal(student, correct):
    student = normalize_answer(student)
    correct = normalize_answer(correct)
    try:
        s_expr = sp.sympify(student)
        c_expr = sp.sympify(correct)
        return sp.simplify(s_expr - c_expr) == 0
    except:
        s_val = safe_eval(student)
        c_val = safe_eval(correct)
        if s_val is not None and c_val is not None:
            return abs(s_val - c_val) < 1e-6
        return student.lower() == correct.lower()

def check_answer(student, correct):
    student = normalize_answer(student)
    if isinstance(correct, list):
        return any(_is_equal(student, ans) for ans in correct)
    else:
        return _is_equal(student, correct)

# ================================
# 生徒画面
# ================================
def main_test():
    st.title("数学自動採点テスト")
    load_problems()
    n = len(st.session_state.all_problems)
    if n == 0:
        st.info("問題がまだ登録されていません。")
        return

    if "q_index" not in st.session_state:
        st.session_state.q_index = 0
    if "results" not in st.session_state:
        st.session_state.results = [{} for _ in range(n)]
    if "order" not in st.session_state:
        st.session_state.order = list(range(n))
        random.shuffle(st.session_state.order)

    idx = st.session_state.order[st.session_state.q_index]
    prob = st.session_state.all_problems[idx]

    st.subheader(f"問題 {st.session_state.q_index+1} / {n}")
    st.write(prob["question"])

    prev_ans = st.session_state.results[st.session_state.q_index].get("student_answer", "")
    if prob.get("type") == "選択式" and "options" in prob:
        answer = st.radio("選択してください", prob["options"], index=0, key=f"answer_{st.session_state.q_index}")
    else:
        answer = st.text_input("答えを入力してください", value=prev_ans, key=f"answer_{st.session_state.q_index}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("回答する", key=f"btn_next_{st.session_state.q_index}"):
            st.session_state.results[st.session_state.q_index] = {
                "question": prob["question"],
                "student_answer": answer,
                "correct_answer": prob["answer"],
                "is_correct": check_answer(answer, prob["answer"])
            }
            if st.session_state.q_index < n - 1:
                st.session_state.q_index += 1
    with col2:
        if st.button("前の問題に戻る", key=f"btn_prev_{st.session_state.q_index}"):
            if st.session_state.q_index > 0:
                st.session_state.q_index -= 1

    if all('is_correct' in r for r in st.session_state.results):
        if st.button("結果を確認する", key="btn_result"):
            df_results = []
            for r in st.session_state.results:
                correct = r["correct_answer"]
                if isinstance(correct, list):
                    correct = " / ".join(correct)
                df_results.append({
                    "question": r["question"],
                    "student_answer": r["student_answer"],
                    "correct_answer": correct,
                    "is_correct": r["is_correct"]
                })
            df = pd.DataFrame(df_results)
            st.subheader("あなたの解答結果")
            st.dataframe(df)
            correct_count = df["is_correct"].sum()
            st.write(f"正解数: {correct_count}/{n}  正答率: {correct_count/n*100:.1f}%")

# ================================
# 教師画面
# ================================
def main_teacher():
    st.title("教師ダッシュボード")
    load_problems()
    if "results" not in st.session_state:
        st.session_state.results = []

    st.subheader("■ 現在の問題一覧（編集可能）")
    for i, prob in enumerate(st.session_state.all_problems):
        with st.expander(f"{i+1}. {prob['question']}"):
            q_text = st.text_input("問題文", value=prob['question'], key=f"q_{i}")
            q_ans = st.text_input("答え（リストの場合は [\"a\",\"b\"] 形式）", value=str(prob['answer']), key=f"a_{i}")
            q_unit = st.text_input("単元", value=prob.get("unit",""), key=f"u_{i}")
            q_type = st.selectbox("タイプ", ["選択式","記述式"], index=0 if prob.get("type")=="選択式" else 1, key=f"type_{i}")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("更新", key=f"update_{i}"):
                    try:
                        ans_val = json.loads(q_ans) if q_ans.strip().startswith("[") else q_ans
                    except:
                        ans_val = q_ans
                    st.session_state.all_problems[i] = {
                        "question": q_text,
                        "answer": ans_val,
                        "unit": q_unit,
                        "type": q_type
                    }
                    save_problems()
                    st.success("問題を更新しました")
            with col2:
                if st.button("削除", key=f"delete_{i}"):
                    st.session_state.all_problems.pop(i)
                    save_problems()
                    st.success("問題を削除しました")
                    st.experimental_rerun()

    st.subheader("■ 新規問題追加")
    q_text = st.text_input("問題文", key="new_q")
    q_ans = st.text_input("答え（リストの場合は [\"a\",\"b\"] 形式）", key="new_a")
    q_unit = st.text_input("単元", value="その他", key="new_u")
    q_type = st.selectbox("タイプ", ["選択式","記述式"], key="new_type")
    if st.button("追加"):
        if q_text and q_ans:
            try:
                ans_val = json.loads(q_ans) if q_ans.strip().startswith("[") else q_ans
            except:
                ans_val = q_ans
            st.session_state.all_problems.append({
                "question": q_text,
                "answer": ans_val,
                "unit": q_unit,
                "type": q_type
            })
            save_problems()
            st.success("新しい問題を追加しました")
            st.experimental_rerun()

    st.subheader("■ 生徒の解答結果分析")
    if st.session_state.results:
        df_results = []
        for r in st.session_state.results:
            correct = r["correct_answer"]
            if isinstance(correct, list):
                correct = " / ".join(correct)
            df_results.append({
                "question": r["question"],
                "student_answer": r["student_answer"],
                "correct_answer": correct,
                "is_correct": r["is_correct"]
            })
        df = pd.DataFrame(df_results)
        st.dataframe(df)

        # 問題ごとの正答率
        st.subheader("■ 問題ごとの正答率")
        ranking = df.groupby("question")["is_correct"].mean().reset_index().rename(columns={"is_correct":"正答率"})
        st.dataframe(ranking)

        # 全体正答率
        st.subheader("■ 全体正答率")
        total = df["is_correct"].mean()
        st.write(f"{total*100:.1f}%")
    else:
        st.info("まだ生徒の解答はありません。")

# ================================
# アプリ本体（簡易ログイン）
# ================================
def main():
    st.title("数学学習アプリ")
    mode = st.radio("モードを選択", ["生徒", "教師"])
    if mode=="生徒":
        main_test()
    else:
        pw = st.text_input("教師パスワード", type="password")
        if st.button("ログイン（教師）"):
            if pw == "20020711":
                main_teacher()
            else:
                st.error("パスワードが違います")

if __name__=="__main__":
    main()


