import os
import io
import requests
import pandas as pd
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ✅ تحميل ملف .env
load_dotenv()

# ===================== الإعدادات =====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
EXCEL_FILE = os.getenv("EXCEL_FILE")
SHEET_NAME = "الادخال"
SEARCH_COLUMN = "رقم الاذن"

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN is not set in environment variables.")

# الأعمدة اللي هتظهر في الرد
COLUMNS_TO_SHOW = ["العميل", "المشروع", "رقم الطلب", "سعر الأذن", "المورد", "التاريخ"]

# ===================== تحميل البيانات =====================
def load_dataframe() -> pd.DataFrame:
    """تحميل بيانات الإكسيل سواء من لينك أو من ملف محلي."""
    try:
        if str(EXCEL_FILE).startswith("http"):
            print("📥 تحميل من Google Drive ...")
            response = requests.get(EXCEL_FILE)
            response.raise_for_status()
            df_local = pd.read_excel(io.BytesIO(response.content), sheet_name=SHEET_NAME, engine="openpyxl")
        else:
            print("📄 تحميل من ملف محلي ...")
            df_local = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME, engine="openpyxl")

        df_local = df_local.fillna("")
        if SEARCH_COLUMN in df_local.columns:
            df_local[SEARCH_COLUMN] = df_local[SEARCH_COLUMN].astype(str).str.strip()
        return df_local

    except Exception as e:
        print(f"❌ فشل تحميل الملف: {e}")
        return pd.DataFrame()

# تحميل أولي عند التشغيل
DF = load_dataframe()

# ===================== دوال مساعدة =====================
def format_value(col_name: str, value) -> str:
    """تنسيق التاريخ"""
    if col_name == "التاريخ" and str(value).strip() != "":
        try:
            ts = pd.to_datetime(str(value), errors="coerce", dayfirst=True)
            if pd.notna(ts):
                return ts.strftime("%d-%m-%Y")
        except Exception:
            pass
    return str(value)

def build_reply(row: pd.Series) -> str:
    """يبني الرسالة النهائية"""
    return "\n".join(f"{col}: {format_value(col, row.get(col, ''))}" for col in COLUMNS_TO_SHOW)

# ===================== الأوامر =====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 ابعت رقم الإذن وهجيبلك البيانات.\n"
        "لو الملف اتحدث: /reload لإعادة التحميل."
    )

async def reload_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global DF
    DF = load_dataframe()
    if DF.empty:
        await update.message.reply_text("❌ فشل تحميل الملف. تأكد من الرابط.")
    else:
        await update.message.reply_text("✅ تم إعادة تحميل الملف.")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = (update.message.text or "").strip()
    if not query:
        return
    if DF.empty:
        await update.message.reply_text("⚠️ الملف غير محمل. استخدم /reload.")
        return
    if SEARCH_COLUMN not in DF.columns:
        await update.message.reply_text(f"❌ مش لاقي العمود '{SEARCH_COLUMN}'.")
        return

    results = DF[DF[SEARCH_COLUMN].astype(str).str.strip() == query]
    if results.empty:
        await update.message.reply_text("❌ الرقم مش موجود")
        return

    reply = build_reply(results.iloc[0])
    await update.message.reply_text(reply)

# ===================== تشغيل البوت =====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reload", reload_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
