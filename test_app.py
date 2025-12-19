import streamlit as st
import json
import random
import pandas as pd
import numpy as np
import sympy as sp
import os
import unicodedata
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# ==============================
# 設定・定数
# ==============================
PROBLEM_FILE = "problems.json"
RESULT_FILE = "results.csv"
TEACHER_PASSWORD = "admin"  # 必要に応じて変更してください

REQUIRED_COLUMNS = [
    "student_id",
    "question",
    "student_answer",
    "correct_answer",
    "is_correct",
    "timestamp",
]

# ==============================
# データ管理・ユーティリティ
# ==============================

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def load_problems():
    if not os.path.exists(PROBLEM_FILE):
        return []
    try:
        with open(PROBLEM_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_problems(problems):
    with open(PROBLEM_FILE, "w", encoding="utf-8") as f:
        json.dump(problems, f, ensure_ascii=False, indent=2)

def load_results():
    if not os.path.exists(RESULT_FILE):
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    try:
        df = pd.read_csv(RESULT_FILE)
        # 【修正ポイント】is_correct 列を確実に数値に変換
        if "is_correct" in df.columns:
            df["is_correct"] = pd.to_numeric(df["is_correct"], errors='coerce')
        return df
    except Exception:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

# ==============================
# 数学的な採点ロジック
# ==============================

def normalize_text(s):
    if not isinstance(s, str): return str(s)
    s = unicodedata.normalize("NFKC", s)
    s = s.strip().replace(" ", "")
    s = s.replace("，", ",").replace("√", "sqrt").replace("π", "pi")
    return s

def is_equal(student, correct):
    s_raw = normalize_text(student)
    c_raw = normalize_text(correct)
    
    if s_raw == c_raw: return True
    
    try:
        if abs(float(s_raw) - float(c_raw)) < 1e-7: return True
    except: pass

    try:
        s_expr = s_raw.replace("x=", "").replace("y=", "")
        c_expr = c_raw.replace("x=", "").replace("y=", "")
        
        if "," in s_expr or "," in c_expr:
            s_set = {sp.simplify(x) for x in s_expr.split(",")}
            c_set = {sp.simplify(x) for x in c_expr.split(",")}
            return s_set == c_set
        
        diff = sp.simplify(f"({s_expr}) - ({c_expr})")
        if diff == 0: return True
    except: pass

    return False

def check_answer(student, correct):
    if isinstance(correct, list):
        return any(is_equal(student, c) for c in correct)
    return is_equal(student, correct)

# ==============================
# 生徒画面
# ==============================

def student_view():
    st.header("✏️ 生徒用テスト")
    
    col_id, _ = st.columns([2, 1])
    student_id = col_id.text_input("生徒IDを入力してください（例：出席番号）")
    
    if not student_id:
        st.info("ログインしてください")
        return

    problems = load_problems()
    if not problems:
        st.warning("現在、公開されている問題はありません。")
        return

    if "order" not in st.session_state:
        st.session_state.order = list(range(len(problems)))
        random.shuffle(st.session_state.order)
        st.session_state.q_idx = 0
        st.session_state.student_results = {}
        st.session_state.submitted = False

    if st.session_state.submitted:
        st.success("テスト完了！お疲れ様でした。")
        if st.button("もう一度受ける"):
            for key in ["order", "q_idx", "student_results", "submitted"]:
                if key in st.session_state: del st.session_state[key]
            st.rerun()
        return

    q_num = st.session_state.q_idx
    prob_idx = st.session_state.order[q_num]
    prob = problems[prob_idx]

    st.subheader(f"問題 {q_num + 1} / {len(problems)}")
    st.info(prob["question"])
    
    answer = st.text_input("答えを入力", key=f"input_{q_num}")
    
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if st.button("← 前へ") and q_num > 0:
            st.session_state.q_idx -= 1
            st.rerun()
    with c2:
        btn_label = "採点して終了" if q_num == len(problems) - 1 else "次へ →"
        if st.button(btn_label):
            correct = check_answer(answer, prob["answer"])
            st.session_state.student_results[prob_idx] = {
                "student_id": student_id,
                "question": prob["question"],
                "student_answer": answer,
                "correct_answer": str(prob["answer"]),
                "is_correct": 1 if correct else 0,
                "timestamp": now()
            }
            
            if q_num < len(problems) - 1:
                st.session_state.q_idx += 1
                st.rerun()
            else:
                new_df = pd.DataFrame(st.session_state.student_results.values())
                new_df.to_csv(RESULT_FILE, mode="a", header=not os.path.exists(RESULT_FILE), index=False)
                st.session_state.submitted = True
                st.rerun()

# ==============================
# 教師画面（分析・管理）
# ==============================

def teacher_view():
    st.header("🧑‍🏫 教師用管理ダッシュボード")
    
    tab1, tab2, tab3 = st.tabs(["📊 成績分析", "📝 問題編集", "⚙️ 設定"])

    with tab1:
        df = load_results()
        if df.empty or "is_correct" not in df.columns:
            st.write("まだ解答データがありません。")
        else:
            # --- 1. 全体統計 ---
            st.subheader("📈 クラス全体の概況")
            
            # 【修正ポイント】NaNを除外して平均を計算
            valid_scores = df["is_correct"].dropna()
            total_accuracy = valid_scores.mean() * 100 if not valid_scores.empty else 0
            
            col1, col2, col3 = st.columns(3)
            col1.metric("全体の平均正答率", f"{total_accuracy:.1f}%")
            col2.metric("総解答数", f"{len(df)} 件")
            col3.metric("受験人数", f"{df['student_id'].nunique()} 人")

            # --- 2. 正答率の分布 (ヒストグラム) ---
            st.write("#### 生徒別正答率の分布")
            student_stats = df.groupby("student_id")["is_correct"].mean() * 100
            fig_dist = px.histogram(
                student_stats, 
                x="is_correct", 
                nbins=10,
                labels={'is_correct': '正答率 (%)', 'count': '人数'},
                title="得点帯ごとの人数分布",
                color_discrete_sequence=['#636EFA']
            )
            fig_dist.update_layout(yaxis_title="人数")
            st.plotly_chart(fig_dist, use_container_width=True)

            # --- 3. 問題ごとの正答率 ---
            st.write("#### 問題ごとの正答率（ワースト順）")
            prob_stats = df.groupby("question")["is_correct"].mean().sort_values() * 100
            fig_prob = px.bar(
                x=prob_stats.values, 
                y=prob_stats.index, 
                orientation='h',
                labels={'x': '正答率 (%)', 'y': ''},
                color=prob_stats.values,
                color_continuous_scale='RdYlGn',
                range_color=[0, 100]
            )
            st.plotly_chart(fig_prob, use_container_width=True)

            # --- 4. 個別生徒の詳細 ---
            st.divider()
            st.subheader("🔍 個別生徒のカルテ")
            target_sid = st.selectbox("生徒IDを選択", sorted(df["student_id"].unique()))
            
            sdf = df[df["student_id"] == target_sid].sort_values("timestamp")
            
            c1, c2 = st.columns([1, 2])
            with c1:
                st.write(f"**生徒ID: {target_sid}**")
                st.write(f"現在の平均正答率: {sdf['is_correct'].mean()*100:.1f}%")
                st.dataframe(sdf[["question", "student_answer", "is_correct"]], hide_index=True)
            
            with c2:
                sdf["cum_accuracy"] = sdf["is_correct"].expanding().mean() * 100
                fig_line = px.line(sdf, x="timestamp", y="cum_accuracy", 
                                   title="学習進捗（正答率の推移）", markers=True)
                fig_line.update_yaxes(range=[0, 105])
                st.plotly_chart(fig_line, use_container_width=True)

    with tab2:
        st.subheader("問題の追加・編集")
        problems = load_problems()
        
        with st.expander("➕ 新規問題を追加"):
            new_q = st.text_area("問題文 (例: $x^2-1=0$ を解け)")
            new_a = st.text_input("正解 (例: 1, -1)")
            if st.button("追加実行"):
                problems.append({"question": new_q, "answer": new_a})
                save_problems(problems)
                st.success("追加しました")
                st.rerun()

        for i, p in enumerate(problems):
            with st.expander(f"問{i+1}: {p['question'][:30]}..."):
                edit_q = st.text_area("問題文", p["question"], key=f"edq_{i}")
                edit_a = st.text_input("正解", p["answer"], key=f"eda_{i}")
                col_s, col_d, _ = st.columns([1, 1, 4])
                if col_s.button("更新", key=f"up_{i}"):
                    problems[i] = {"question": edit_q, "answer": edit_a}
                    save_problems(problems)
                    st.rerun()
                if col_d.button("削除", key=f"del_{i}"):
                    problems.pop(i)
                    save_problems(problems)
                    st.rerun()

    with tab3:
        st.subheader("管理設定")
        if st.button("🗑️ 全成績データをリセット"):
            if os.path.exists(RESULT_FILE):
                os.remove(RESULT_FILE)
                st.success("成績データを全て削除しました。")
                st.rerun()

# ==============================
# メイン
# ==============================

st.set_page_config(page_title="学習データ分析アプリ", layout="wide")

if "mode" not in st.session_state:
    st.session_state.mode = None

with st.sidebar:
    st.title("🍀 メニュー")
    if st.button("🏠 ホーム"):
        st.session_state.mode = None
        st.rerun()
    st.divider()
    if st.button("✏️ 生徒用テスト"):
        st.session_state.mode = "student"
        st.rerun()
    if st.button("🧑‍🏫 教師用ダッシュボード"):
        st.session_state.mode = "teacher_auth"
        st.rerun()

if st.session_state.mode is None:
    st.title("学習データ分析システム")
    st.write("生徒の正答率をリアルタイムで分析し、グラフで可視化します。")
    st.info("左側のメニューから進んでください。")

elif st.session_state.mode == "student":
    student_view()

elif st.session_state.mode == "teacher_auth":
    st.title("教師用認証")
    pw = st.text_input("パスワードを入力", type="password")
    if pw == TEACHER_PASSWORD:
        st.session_state.mode = "teacher"
        st.rerun()
    elif pw != "":
        st.error("パスワードが違います")

elif st.session_state.mode == "teacher":
    teacher_view()