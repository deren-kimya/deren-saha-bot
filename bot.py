import os
import logging
import socket
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import pymysql

# ===========================================
# LOGGER AYARLARI
# ===========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===========================================
# RAILWAY IP'SİNİ ÖĞREN VE LOGLA
# ===========================================
def log_railway_ip():
    """Railway'in IP adreslerini öğren ve logla"""
    try:
        # Local IP
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        logger.info(f"🌐 Railway Local IP: {local_ip}")
        
        # Public IP (Railway'in dış dünyaya çıktığı IP)
        response = requests.get('https://api.ipify.org?format=json', timeout=5)
        public_ip = response.json()['ip']
        logger.info(f"🌍 Railway Public IP: {public_ip}")
        logger.info(f"⭐⭐⭐ BU IP'YI PLESK'TE WHITELIST'E EKLEYİN: {public_ip} ⭐⭐⭐")
        
        return public_ip
    except Exception as e:
        logger.error(f"❌ IP öğrenilemedi: {e}")
        return None

# Bot başlatıldığında IP'yi logla
logger.info("=" * 60)
logger.info("🤖 GÜVENLİ BOT BAŞLATILIYOR...")
logger.info("=" * 60)
railway_ip = log_railway_ip()
logger.info("=" * 60)

# ===========================================
# ENVIRONMENT VARIABLES
# ===========================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8351485945:AAHTEv5C2RLdQtR9NtyZI_qPUwVWcv1orog')
DB_HOST = os.getenv('DB_HOST', '94.102.75.134')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_USER = os.getenv('DB_USER', 'alpeRAdnin')
DB_PASS = os.getenv('DB_PASS', 'thT7&-HHbfYUa')
DB_NAME = os.getenv('DB_NAME', 'derenkimya_membran')

# ===========================================
# DATABASE BAĞLANTI FONKSİYONU
# ===========================================
def get_db_connection():
    """MySQL veritabanı bağlantısı oluştur"""
    try:
        connection = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10
        )
        return connection
    except Exception as e:
        logger.error(f"Database bağlantı hatası: {e}")
        return None

# ===========================================
# YETKİ KONTROLÜ
# ===========================================
def is_user_authorized(telegram_id: int) -> tuple:
    """
    Kullanıcının konum gönderme yetkisi var mı kontrol et
    Returns: (authorized: bool, user_name: str, user_role: str)
    """
    connection = get_db_connection()
    if not connection:
        return False, None, None
    
    try:
        with connection.cursor() as cursor:
            # telegram_user_mapping ve users tablosundan kullanıcı bilgisi al
            query = """
                SELECT 
                    tum.user_id,
                    tum.telegram_id,
                    tum.is_active,
                    u.name as user_name,
                    u.role as user_role
                FROM telegram_user_mapping tum
                JOIN users u ON tum.user_id = u.user_id
                WHERE tum.telegram_id = %s 
                AND tum.is_active = 1
            """
            cursor.execute(query, (telegram_id,))
            result = cursor.fetchone()
            
            if not result:
                logger.warning(f"❌ Yetkisiz erişim denemesi: {telegram_id}")
                return False, None, None
            
            # MÜŞTERİ KONTROLÜ
            if result['user_role'] == 'Müşteri':
                logger.warning(f"❌ Müşteri konum gönderemez: {telegram_id} ({result['user_name']})")
                return False, result['user_name'], result['user_role']
            
            logger.info(f"✅ Yetkili kullanıcı: {result['user_name']} (Role: {result['user_role']})")
            return True, result['user_name'], result['user_role']
            
    except Exception as e:
        logger.error(f"Yetki kontrolü hatası: {e}")
        return False, None, None
    finally:
        connection.close()

# ===========================================
# KONUM KAYDETME FONKSİYONU
# ===========================================
def save_location_to_db(telegram_id: int, user_name: str, latitude: float, longitude: float, phone: str = None):
    """Konumu veritabanına kaydet"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            # Kullanıcının user_id'sini al
            cursor.execute(
                "SELECT user_id FROM telegram_user_mapping WHERE telegram_id = %s",
                (telegram_id,)
            )
            user_result = cursor.fetchone()
            
            if not user_result:
                logger.error(f"User ID bulunamadı: {telegram_id}")
                return False
            
            user_id = user_result['user_id']
            
            # Konum verisini kaydet
            query = """
                INSERT INTO field_visits 
                (user_id, telegram_id, user_name, latitude, longitude, phone, visit_date)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """
            cursor.execute(query, (user_id, telegram_id, user_name, latitude, longitude, phone))
            connection.commit()
            
            logger.info(f"✅ Konum kaydedildi: {user_name} - {latitude}, {longitude}")
            return True
            
    except Exception as e:
        logger.error(f"Konum kaydetme hatası: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()

# ===========================================
# TELEGRAM BOT KOMUTLARI
# ===========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start komutu"""
    telegram_id = update.effective_user.id
    user_name = update.effective_user.full_name
    
    logger.info(f"👤 /start komutu: {user_name} (ID: {telegram_id})")
    
    # Yetki kontrolü
    authorized, db_user_name, user_role = is_user_authorized(telegram_id)
    
    if not authorized:
        if user_role == 'Müşteri':
            await update.message.reply_text(
                f"❌ Merhaba {user_name},\n\n"
                "Müşteriler konum gönderemez.\n"
                "Sadece satış temsilcileri ve yöneticiler konum paylaşabilir."
            )
        else:
            await update.message.reply_text(
                f"❌ Merhaba {user_name},\n\n"
                "Bu botu kullanma yetkiniz yok.\n"
                "Lütfen sistem yöneticisiyle iletişime geçin."
            )
        return
    
    await update.message.reply_text(
        f"✅ Merhaba {db_user_name}!\n\n"
        f"Rolünüz: {user_role}\n\n"
        "Saha ziyareti yaparken konumunuzu paylaşabilirsiniz.\n\n"
        "📍 Telegram'ın konum paylaşma özelliğini kullanarak anlık konumunuzu gönderin."
    )

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Konum mesajlarını işle"""
    telegram_id = update.effective_user.id
    user_name = update.effective_user.full_name
    
    logger.info(f"📍 Konum alındı: {user_name} (ID: {telegram_id})")
    
    # Yetki kontrolü
    authorized, db_user_name, user_role = is_user_authorized(telegram_id)
    
    if not authorized:
        if user_role == 'Müşteri':
            logger.warning(f"❌ Müşteri konum gönderme denemesi: {telegram_id} ({user_name})")
            await update.message.reply_text(
                "❌ Müşteriler konum gönderemez.\n"
                "Sadece satış temsilcileri ve yöneticiler konum paylaşabilir."
            )
        else:
            logger.warning(f"❌ Yetkisiz konum gönderme denemesi: {telegram_id} ({user_name})")
            await update.message.reply_text(
                "❌ Bu işlem için yetkiniz yok.\n"
                "Lütfen sistem yöneticisiyle iletişime geçin."
            )
        return
    
    # Konum bilgilerini al
    location = update.message.location
    latitude = location.latitude
    longitude = location.longitude
    
    # Telefon numarasını al (varsa)
    phone = None
    if update.effective_user.username:
        phone = update.effective_user.username
    
    # Veritabanına kaydet
    success = save_location_to_db(telegram_id, db_user_name, latitude, longitude, phone)
    
    if success:
        google_maps_url = f"https://www.google.com/maps?q={latitude},{longitude}"
        await update.message.reply_text(
            f"✅ Konum başarıyla kaydedildi!\n\n"
            f"👤 İsim: {db_user_name}\n"
            f"📍 Koordinatlar: {latitude}, {longitude}\n"
            f"🗺️ Harita: {google_maps_url}\n\n"
            f"Teşekkürler! 🙏"
        )
    else:
        await update.message.reply_text(
            "❌ Konum kaydedilemedi.\n"
            "Lütfen tekrar deneyin veya sistem yöneticisiyle iletişime geçin."
        )

# ===========================================
# ANA FONKSİYON
# ===========================================
def main():
    """Bot'u başlat"""
    logger.info("🔒 Whitelist sistemi aktif")
    logger.info("🚀 Bot başlatılıyor...")
    
    # Application oluştur
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Komut handler'ları ekle
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.LOCATION, handle_location))
    
    # Bot'u çalıştır
    logger.info("✅ Bot çalışıyor...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
