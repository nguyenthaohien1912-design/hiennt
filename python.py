# app.py

import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from docx import Document
from google import genai
from google.genai.errors import APIError

# ============ Cấu hình Trang ============ #
st.set_page_config(page_title="Đánh giá Phương án Kinh doanh", layout="wide")
st.title("📘 ỨNG DỤNG PHÂN TÍCH PHƯƠNG ÁN KINH DOANH (WORD)")

# ============ Hàm Đọc nội dung file Word ============ #
def read_word(file):
    doc = Document(file)
    full_text = []
    for para in doc.paragraphs:
        if para.text.strip():
            full_text.append(para.text.strip())
    return "\n".join(full_text)

# ============ Hàm Gọi AI để Trích xuất thông tin dự án ============ #
def extract_project_info(text, api_key):
    try:
        client = genai.Client(api_key=api_key)
        model_name = "gemini-2.5-flash"

        prompt = f"""
        Bạn là chuyên gia tài chính. Hãy trích xuất các thông tin sau từ nội dung file Word dưới đây:
        - Vốn đầu tư (tỷ đồng)
        - Dòng đời dự án (năm)
        - Doanh thu hàng năm (tỷ đồng)
        - Chi phí hàng năm (tỷ đồng)
        - WACC (%)
        - Thuế suất (%)

        Chỉ trả về kết quả theo dạng JSON ngắn gọn như ví dụ:
        {{
          "Vốn đầu tư": 30,
          "Dòng đời dự án": 10,
          "Doanh thu": 3.5,
          "Chi phí": 2.0,
          "WACC": 13,
          "Thuế": 20
        }}

        Nội dung file Word:
        {text}
        """

        response = client.models.generate_content(model=model_name, contents=prompt)
        return response.text

    except APIError as e:
        return f"Lỗi gọi Gemini API: {e}"
    except Exception as e:
        return f"Lỗi không xác định: {e}"

# ============ Hàm Tạo bảng dòng tiền ============ #
def build_cashflow(data):
    years = list(range(1, int(data['Dòng đời dự án']) + 1))
    revenue = [data['Doanh thu']] * len(years)
    cost = [data['Chi phí']] * len(years)
    tax_rate = data['Thuế'] / 100
    invest = data['Vốn đầu tư']

    net_profit = []
    cash_flow = []

    for i in range(len(years)):
        profit_before_tax = revenue[i] - cost[i]
        profit_after_tax = profit_before_tax * (1 - tax_rate)
        net_profit.append(profit_after_tax)
        cash_flow.append(profit_after_tax)

    # Thêm dòng đầu tư ban đầu
    cash_flow = [-invest] + cash_flow
    years = [0] + years

    df = pd.DataFrame({
        "Năm": years,
        "Doanh thu": [0] + revenue,
        "Chi phí": [0] + cost,
        "Lợi nhuận sau thuế": [0] + net_profit,
        "Dòng tiền": cash_flow
    })
    return df

# ============ Hàm Tính chỉ số tài chính ============ #
def calc_financial_metrics(df, wacc):
    cash_flows = df["Dòng tiền"].values
    years = df["Năm"].values

    # NPV
    npv = np.npv(wacc/100, cash_flows)

    # IRR
    irr = np.irr(cash_flows) * 100

    # PP (Payback Period)
    cumulative = np.cumsum(cash_flows)
    try:
        pp = next(years[i] for i, val in enumerate(cumulative) if val >= 0)
    except StopIteration:
        pp = None

    # DPP (Discounted Payback Period)
    discounted_cf = [cf / ((1 + wacc/100) ** y) for y, cf in zip(years, cash_flows)]
    cumulative_dcf = np.cumsum(discounted_cf)
    try:
        dpp = next(years[i] for i, val in enumerate(cumulative_dcf) if val >= 0)
    except StopIteration:
        dpp = None

    return npv, irr, pp, dpp

# ============ Hàm Phân tích AI chỉ số hiệu quả ============ #
def ai_analyze_project(npv, irr, pp, dpp, api_key):
    try:
        client = genai.Client(api_key=api_key)
        model_name = "gemini-2.5-flash"
        prompt = f"""
        Hãy đóng vai chuyên gia đầu tư. Dựa trên các chỉ số hiệu quả sau:
        - NPV: {npv:,.2f} tỷ
        - IRR: {irr:.2f}%
        - PP: {pp} năm
        - DPP: {dpp} năm

        Hãy đưa ra nhận xét ngắn gọn (3-4 đoạn) về mức độ khả thi và hiệu quả tài chính của dự án này.
        """

        response = client.models.generate_content(model=model_name, contents=prompt)
        return response.text
    except Exception as e:
        return f"Lỗi phân tích AI: {e}"

# ============ Giao diện chính ============ #
api_key = st.secrets.get("GEMINI_API_KEY")
uploaded_file = st.file_uploader("📎 Tải file Word phương án kinh doanh", type=["docx"])

if uploaded_file:
    st.success("✅ File đã tải lên thành công.")
    text = read_word(uploaded_file)

    if st.button("📄 Trích xuất thông tin dự án (AI)"):
        with st.spinner("Đang xử lý bằng AI..."):
            extracted = extract_project_info(text, api_key)
            st.code(extracted, language="json")

            try:
import json
import re

# Làm sạch chuỗi AI trả về (loại bỏ markdown ```json … ```)
clean_text = re.sub(r"```[a-zA-Z]*", "", extracted)
clean_text = clean_text.replace("```", "").strip()

# Thay 'null' thành 'null' JSON hợp lệ
clean_text = clean_text.replace("null", "null")

try:
    data = json.loads(clean_text)
except json.JSONDecodeError as e:
    st.error(f"Lỗi định dạng JSON từ AI: {e}")
    st.stop()

                df_cf = build_cashflow(data)

                st.subheader("📊 Bảng Dòng Tiền Dự Án")
                st.dataframe(df_cf.style.format("{:,.2f}"), use_container_width=True)

                npv, irr, pp, dpp = calc_financial_metrics(df_cf, data['WACC'])
                st.subheader("📈 Các Chỉ Số Hiệu Quả Dự Án")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("NPV (tỷ đồng)", f"{npv:,.2f}")
                col2.metric("IRR (%)", f"{irr:.2f}")
                col3.metric("PP (năm)", pp)
                col4.metric("DPP (năm)", dpp)

                if st.button("🧠 Yêu cầu AI phân tích hiệu quả dự án"):
                    with st.spinner("AI đang phân tích..."):
                        ai_result = ai_analyze_project(npv, irr, pp, dpp, api_key)
                        st.markdown("### 💡 Nhận xét từ AI:")
                        st.info(ai_result)

            except Exception as e:
                st.error(f"Lỗi khi đọc kết quả AI: {e}")
else:
    st.info("Vui lòng tải file Word để bắt đầu đánh giá.")

