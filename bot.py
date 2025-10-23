import os
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import pymysql

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
SHEET_ID = os.environ.get('SHEET_ID')
GOOGLE_CREDS = os.environ.get('GOOGLE_CREDENTIALS')

DB_HOST = os.environ.get('DB_HOST', '94.102.75.134')
DB_PORT = int(os.environ.get('DB_PORT', '3306'))
DB_USER = os.environ.get('DB_USER', 'alpeRAdnin')
DB_PASS = os.environ.get('DB_PASS', 'thT7&-HHbfYUa')
DB_NAME = os.environ.get('DB_NAME', 'derenkimya_membran')

def get_db_connection():
    try:
        return pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
    except Exception as e:
        logger.error(f"Database bağlantı hatası: {e}")
        return None

def is_user_authorized(telegram_user_id):
    conn = get_db_connection()
    if not conn:
        logger.warning("Database bağlantısı yok, whitelist kontrolü yapılamadı!")
        return False
    
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT tum.id, tum.user_id, u.full_name, u.is_active as user_active
                FROM telegram_user_mapping tum
                LEFT JOIN users u ON tum.user_id = u.id
                WHERE tum.telegram_user_id = %s 
                AND tum.is_active = 1
                LIMIT 1
            """
            cursor.execute(sql, (telegram_user_id,))
            result = cursor.fetchone()
            
            if result:
                if result['user_active'] == 1 or result['user_active'] is None:
                    logger.info(f"✅ Yetkili kullanıcı: {telegram_user_id} ({result['full_name']})")
                    return True
                else:
                    logger.warning(f"❌ Kullanıcı pasif: {telegram_user_id}")
                    return False
            else:
                logger.warning(f"❌ Yetkisiz erişim denemesi: {telegram_user_id}")
                return False
                
    except Exception as e:
        logger.error(f"Yetki kontrolü hatası: {e}")
        return False
    finally:
        conn.close()

def get_sheet():
    try:
        creds_dict = json.loads(GOOGLE_CREDS)
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1
        return sheet
    except Exception as e:
        logger.error(f"Sheets bağlantı hatası: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    
    if not is_user_authorized(user.id):
        await update.message.reply_text(
            "🚫 Yetkisiz Erişim\n\n"
            "Bu bot sadece Deren Kimya satış temsilcileri için aktiftir.\n\n"
            f"📱 Telegram ID'niz: {user.id}\n\n"
            "Eğer satış temsilcisiyseniz, bu ID'yi yöneticinize gönderin."
        )
        logger.warning(f"Yetkisiz /start denemesi: {user.id} ({user.first_name})")
        return
    
    await update.message.reply_text(
        "🚀 Deren Kimya Saha Takip Bot'a Hoş Geldiniz!\n\n"
        "✅ Sisteme kayıtlısınız.\n\n"
        "📍 Konum göndermek için:\n"
        "1. Mesaj kutusundaki 📎 ikonuna tıklayın\n"
        "2. 'Konum' seçeneğini seçin\n"
        "3. Mevcut konumunuzu paylaşın\n\n"
        "✅ Konumunuz otomatik olarak kaydedilecektir."
    )

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    authorized = is_user_authorized(user.id)
    status = "✅ Kayıtlı" if authorized else "❌ Kayıtsız"
    
    await update.message.reply_text(
        f"📱 Telegram Bilgileriniz:\n\n"
        f"🆔 ID: {user.id}\n"
        f"👤 Ad: {user.first_name} {user.last_name or ''}\n"
        f"🔤 Kullanıcı Adı: @{user.username or 'Yok'}\n\n"
        f"📊 Durum: {status}"
    )

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    
    if not is_user_authorized(user.id):
        await update.message.reply_text(
            "🚫 Yetkiniz Yok\n\n"
            "Konum gönderme yetkiniz bulunmamaktadır.\n"
            "Satış temsilcisi iseniz yöneticinizle iletişime geçin.\n\n"
            f"Telegram ID: {user.id}"
        )
        logger.warning(f"❌ Yetkisiz konum gönderme denemesi: {user.id} ({user.first_name})")
        return
    
    try:
        location = update.message.location
        timestamp = update.message.date
        
        latitude = location.latitude
        longitude = location.longitude
        user_name = f"{user.first_name} {user.last_name if user.last_name else ''}".strip()
        user_id = user.id
        maps_link = f"https://www.google.com/maps?q={latitude},{longitude}"
        tr_time = timestamp.strftime('%d.%m.%Y %H:%M:%S')
        
        sheet = get_sheet()
        if sheet:
            sheet.append_row([
                tr_time,
                user_name,
                str(user_id),
                str(latitude),
                str(longitude),
                maps_link,
                '',
                ''
            ])
            
            logger.info(f"✅ Konum kaydedildi: {user_name} (ID: {user_id}) - {maps_link}")
            
            await update.message.reply_text(
                f"✅ Konum kaydedildi!\n\n"
                f"📍 {maps_link}\n"
                f"🕐 {tr_time}"
            )
        else:
            await update.message.reply_text("❌ Sheets bağlantısı kurulamadı. Lütfen tekrar deneyin.")
            
    except Exception as e:
        logger.error(f"Konum işleme hatası: {e}")
        await update.message.reply_text("❌ Bir hata oluştu. Lütfen tekrar deneyin.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    
    if not is_user_authorized(user.id):
        await update.message.reply_text(
            "🚫 Bu bot sadece Deren Kimya satış temsilcileri içindir.\n\n"
            f"Telegram ID: {user.id}"
        )
        return
    
    await update.message.reply_text(
        "❌ Sadece konum kabul edilmektedir.\n\n"
        "📍 Konum göndermek için mesaj kutusundaki 📎 ikonuna tıklayın."
    )

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("myid", myid))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logger.info("🤖 Güvenli Bot başlatılıyor...")
    logger.info("🔒 Whitelist sistemi aktif")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
