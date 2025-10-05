import os
import pandas as pd
import requests
from io import BytesIO
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from flask import Flask
from threading import Thread

# ===================== الإعداد =====================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
EXCEL_FILE = os.getenv("EXCEL_FILE")
SHEET_MAIN = "الادخال"
SHEET_REPORT = "حالة الأوردرات"
SEARCH_COLUMN = "رقم الاذن"
COLUMNS_TO_SHOW = ["العميل", "المشروع", "رقم الطلب", "سعر الأذن", "المورد", "التاريخ"]

# ===================== Flask لتشغيل البوت على Render =====================
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot is running on Render"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# ===================== تحميل البيانات =====================
def load_dataframe(sheet_name=SHEET_MAIN) -> pd.DataFrame:
    try:
        response = requests.get(EXCEL_FILE)
        response.raise_for_status()
        df = pd.read_excel(BytesIO(response.content), sheet_name=sheet_name, engine="openpyxl")
        df = df.fillna("")
        return df
    except Exception as e:
        print(f"⚠️ خطأ في تحميل الشيت {sheet_name}: {e}")
        return pd.DataFrame()

df_main = load_dataframe(SHEET_MAIN)
df_report = load_dataframe(SHEET_REPORT)

# ===================== أمر /start =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 أهلاً! استخدم:\n/اذن <رقم> → لعرض بيانات الإذن\n/حصر → لتوليد تقارير الموردين PDF")

# ===================== أمر /اذن =====================
async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = (update.message.text or "").strip()
    if not query.isdigit():
        await update.message.reply_text("❌ من فضلك ارسل رقم الإذن فقط.")
        return

    global df_main
    result = df_main[df_main[SEARCH_COLUMN].astype(str) == query]
    if result.empty:
        await update.message.reply_text("❌ رقم الإذن غير موجود.")
        return

    row = result.iloc[0]
    if "التاريخ" in row and isinstance(row["التاريخ"], pd.Timestamp):
        row["التاريخ"] = row["التاريخ"].strftime("%d-%m-%Y")

    response = "\n".join([f"{col}: {row[col]}" for col in COLUMNS_TO_SHOW if col in row])
    await update.message.reply_text(f"✅ البيانات:\n{response}")

# ===================== توليد PDF =====================
def create_pdf(df: pd.DataFrame, supplier_name: str, filename: str):
    data = [list(df.columns)] + df.values.tolist()
    pdf = SimpleDocTemplate(filename, pagesize=landscape(A4))
    table = Table(data, repeatRows=1)
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.black)
    ])
    table.setStyle(style)
    pdf.build([Paragraph(f"تقرير المورد: {supplier_name}", getSampleStyleSheet()["Heading3"]), table])
    return filename

# ===================== أمر /حصر =====================
async def generate_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global df_report
    if df_report.empty:
        await update.message.reply_text("⚠️ ملف الأوردرات غير متاح حالياً.")
        return

    for supplier in ["خالد عبودة", "مصنع بدر"]:
        subset = df_report[df_report["المورد"] == supplier]
        if subset.empty:
            await update.message.reply_text(f"❌ لا توجد بيانات للمورد {supplier}.")
            continue

        filename = f"{supplier.replace(' ', '_')}.pdf"
        create_pdf(subset, supplier, filename)
        await update.message.reply_document(document=open(filename, "rb"), filename=filename)
        os.remove(filename)

# ===================== التحديث التلقائي =====================
def auto_reload():
    global df_main, df_report
    print("⏱️ تحديث البيانات من Google Drive...")
    df_main = load_dataframe(SHEET_MAIN)
    df_report = load_dataframe(SHEET_REPORT)
    print("✅ تم التحديث بنجاح.")

scheduler = BackgroundScheduler()
scheduler.add_job(auto_reload, "interval", minutes=1)
scheduler.start()

# ===================== تشغيل البوت =====================
def run_bot():
    app_bot = Application.builder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("حصر", generate_report))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
    print("🤖 Bot is running...")
    app_bot.run_polling()

if __name__ == "__main__":
    Thread(target=run_flask).start()
    run_bot()
