import os
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import mysql.connector
from mysql.connector import Error

# ===========================================
# LOGGER AYARLARI
# ===========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logger.info("=" * 60)
logger.info("🤖 SAHA ZİYARET BOT BAŞLATILIYOR (MySQL Direkt)...")
logger.info("=" * 60)

# ===========================================
# ENVIRONMENT VARIABLES
# ===========================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASS')
DB_PORT = os.getenv('DB_PORT', '3306')

# ===========================================
# MYSQL BAĞLANTISI
# ===========================================
def get_db_connection():
    """MySQL bağlantısı oluştur"""
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            port=int(DB_PORT),
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        
        if connection.is_connected():
            logger.info("✅ MySQL bağlantısı başarılı")
            return connection
        
    except Error as e:
        logger.error(f"❌ MySQL bağlantı hatası: {e}")
        return None

# ===========================================
# KONUM KAYDETME
# ===========================================
def save_location_to_db(telegram_id: int, user_name: str, latitude: float, longitude: float):
    """Konumu MySQL'e kaydet"""
    try:
        connection = get_db_connection()
        if not connection:
            logger.error("❌ Database bağlantısı yok")
            return False
        
        cursor = connection.cursor()
        
        # 🔒 WHİTELİST KONTROLÜ
        check_query = """
            SELECT tum.user_id, u.user_type 
            FROM telegram_user_mapping tum
            JOIN users u ON tum.user_id = u.id
            WHERE tum.telegram_user_id = %s 
            AND tum.is_active = 1
            LIMIT 1
        """
        
        cursor.execute(check_query, (telegram_id,))
        user_mapping = cursor.fetchone()
        
        # ❌ Kullanıcı whitelist'te değil
        if not user_mapping:
            logger.warning(f"⚠️  Yetkisiz kullanıcı: {user_name} (ID: {telegram_id})")
            cursor.close()
            connection.close()
            return False
        
        user_id, user_type = user_mapping
        
        # ❌ Müşteri ise kaydetme
        if user_type == 'customer':
            logger.warning(f"⚠️  Müşteri atlandı: {user_name} (ID: {telegram_id})")
            cursor.close()
            connection.close()
            return False
        
        # ✅ Konumu kaydet
        visit_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        google_maps_url = f"https://www.google.com/maps?q={latitude},{longitude}"
        
        insert_query = """
            INSERT INTO field_visits 
            (user_id, telegram_user_id, latitude, longitude, visit_date, maps_link, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """
        
        cursor.execute(insert_query, (
            user_id,
            telegram_id,
            latitude,
            longitude,
            visit_date,
            google_maps_url
        ))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        logger.info(f"✅ Konum kaydedildi: {user_name} | {latitude},{longitude}")
        return True
        
    except Error as e:
        logger.error(f"❌ Konum kaydetme hatası: {e}")
        return False

# ===========================================
# TELEGRAM BOT KOMUTLARI
# ===========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start komutu"""
    user_name = update.effective_user.full_name
    telegram_id = update.effective_user.id
    
    logger.info(f"👤 /start komutu: {user_name} (ID: {telegram_id})")
    
    await update.message.reply_text(
        f"✅ Merhaba {user_name}!\n\n"
        "Saha ziyareti sırasında konumunuzu paylaşabilirsiniz.\n\n"
        "📍 Telegram'ın konum paylaşma özelliğini kullanarak "
        "anlık konumunuzu gönderin.\n\n"
        "🔒 Sadece yetkili kullanıcıların konumları kaydedilir."
    )

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Konum mesajlarını işle"""
    telegram_id = update.effective_user.id
    user_name = update.effective_user.full_name
    
    logger.info(f"📍 Konum alındı: {user_name} (ID: {telegram_id})")
    
    # Konum bilgilerini al
    location = update.message.location
    latitude = location.latitude
    longitude = location.longitude
    
    # MySQL'e kaydet (whitelist kontrolü fonksiyon içinde)
    success = save_location_to_db(telegram_id, user_name, latitude, longitude)
    
    if success:
        google_maps_url = f"https://www.google.com/maps?q={latitude},{longitude}"
        await update.message.reply_text(
            f"✅ Konum başarıyla kaydedildi!\n\n"
            f"👤 {user_name}\n"
            f"📍 {latitude}, {longitude}\n"
            f"🗺️ {google_maps_url}\n\n"
            f"Teşekkürler! 🙏"
        )
    else:
        await update.message.reply_text(
            "⚠️ Konum kaydedilemedi.\n\n"
            "Lütfen sistem yöneticinizle iletişime geçin.\n"
            "Yalnızca yetkili kullanıcılar konum gönderebilir."
        )

# ===========================================
# ANA FONKSİYON
# ===========================================
def main():
    """Bot'u başlat"""
    logger.info("🚀 Bot başlatılıyor...")
    logger.info("🔒 Güvenlik: Whitelist kontrolü AKTİF")
    logger.info("💾 Veritabanı: MySQL Direkt Kayıt")
    logger.info("📊 Google Sheets: KULLANILMIYOR")
    
    # Application oluştur
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Handler'ları ekle
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))
    
    # Bot'u çalıştır
    logger.info("✅ Bot çalışıyor ve konum bekliyor...")
    logger.info("=" * 60)
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
