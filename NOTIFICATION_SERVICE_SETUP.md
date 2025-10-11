# 📧 **NOTIFICATION SERVICE SETUP GUIDE**

This guide explains how to configure email and SMS notifications for the Prontivus platform.

---

## 📋 **OVERVIEW**

The notification service supports:
- **Email:** SendGrid, AWS SES, or Mock (test mode)
- **SMS:** Twilio, AWS SNS, or Mock (test mode)

Notifications are sent for:
- ✅ Appointment request approved/rejected
- ✅ Appointment reminders (24 hours before)
- ⚠️ Prescription ready (future)
- ⚠️ Test results available (future)

---

## 🚀 **QUICK START (MOCK MODE - TESTING)**

By default, the system runs in **MOCK mode**, which means notifications are only logged, not actually sent.

**To test without real providers:**
1. No configuration needed
2. Check backend logs to see "mock" notifications

**Environment Variables (default):**
```bash
EMAIL_PROVIDER=mock
SMS_PROVIDER=mock
```

---

## 📧 **EMAIL CONFIGURATION**

### **Option 1: SendGrid (Recommended)**

SendGrid is the easiest to set up and offers 100 free emails/day.

**Steps:**
1. Create a SendGrid account: https://signup.sendgrid.com
2. Go to Settings → API Keys → Create API Key
3. Give it "Full Access" permissions
4. Copy the API key

**Environment Variables:**
```bash
EMAIL_PROVIDER=sendgrid
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxx
EMAIL_FROM=noreply@prontivus.com.br
```

**Install Python Library:**
```bash
pip install sendgrid
```

**Test:**
```bash
curl -X POST http://localhost:8000/api/v1/test-notification \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "subject": "Test", "message": "Hello World"}'
```

---

### **Option 2: AWS SES (Amazon Simple Email Service)**

Best for high volume, requires AWS account.

**Steps:**
1. Create AWS account: https://aws.amazon.com
2. Go to AWS SES → Verified Identities
3. Add and verify your "From" email address
4. Configure IAM credentials with SES permissions

**Environment Variables:**
```bash
EMAIL_PROVIDER=aws_ses
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
EMAIL_FROM=noreply@prontivus.com.br
```

**Install Python Library:**
```bash
pip install boto3
```

**Note:** AWS SES starts in "Sandbox Mode" (can only send to verified emails). Request production access in AWS Console.

---

## 📱 **SMS CONFIGURATION**

### **Option 1: Twilio (Recommended for Global)**

Twilio is the most reliable SMS provider globally.

**Steps:**
1. Create Twilio account: https://www.twilio.com/try-twilio
2. Get $15 free credit (enough for ~1000 SMS)
3. Go to Console → Get a Twilio phone number
4. Copy Account SID and Auth Token

**Environment Variables:**
```bash
SMS_PROVIDER=twilio
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM_NUMBER=+15551234567
```

**Install Python Library:**
```bash
pip install twilio
```

**Test:**
```bash
curl -X POST http://localhost:8000/api/v1/test-sms \
  -H "Content-Type: application/json" \
  -d '{"phone": "+5511999999999", "message": "Test SMS"}'
```

**Pricing:**
- Brazil: ~$0.045 per SMS
- USA: ~$0.0075 per SMS

---

### **Option 2: AWS SNS (Brazilian Market)**

AWS SNS is cheaper for Brazilian SMS.

**Steps:**
1. Create AWS account
2. Configure IAM credentials with SNS permissions
3. Enable SMS in AWS SNS

**Environment Variables:**
```bash
SMS_PROVIDER=aws_sns
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
```

**Install Python Library:**
```bash
pip install boto3
```

**Pricing:**
- Brazil: ~$0.025 per SMS

---

### **Option 3: Brazilian SMS Providers**

For Brazilian market, you may prefer local providers:
- **Zenvia**: https://www.zenvia.com
- **Total Voice**: https://totalvoice.com.br
- **Smsdev**: https://www.smsdev.com.br

**Note:** These are not implemented yet. You can extend `NotificationProvider` class to add custom providers.

---

## 🔧 **RENDER.COM DEPLOYMENT SETUP**

### **Environment Variables in Render:**

1. Go to Render Dashboard → Your Service → Environment
2. Add the following variables:

**For SendGrid:**
```
EMAIL_PROVIDER = sendgrid
SENDGRID_API_KEY = SG.xxxxxxxxxxxxxxxxxxxxx
EMAIL_FROM = noreply@prontivus.com.br
```

**For Twilio:**
```
SMS_PROVIDER = twilio
TWILIO_ACCOUNT_SID = AC...
TWILIO_AUTH_TOKEN = ...
TWILIO_FROM_NUMBER = +15551234567
```

3. Click "Save Changes"
4. Render will automatically redeploy

---

## 🧪 **TESTING NOTIFICATIONS**

### **Test Email Notification:**
```python
# Python script
import asyncio
from app.services.notification_service import notification_service

async def test_email():
    result = await notification_service.send_email(
        to="test@example.com",
        subject="Test Email",
        message="This is a test email from Prontivus",
        html_content="<h1>Test</h1><p>This is a test email</p>"
    )
    print(result)

asyncio.run(test_email())
```

### **Test SMS Notification:**
```python
# Python script
import asyncio
from app.services.notification_service import notification_service

async def test_sms():
    result = await notification_service.send_sms(
        to="+5511999999999",
        message="This is a test SMS from Prontivus"
    )
    print(result)

asyncio.run(test_sms())
```

### **Test Appointment Reminder:**
```python
# Python script
import asyncio
from datetime import datetime, timedelta
from app.services.notification_service import notification_service

async def test_reminder():
    result = await notification_service.send_appointment_reminder(
        patient_email="patient@example.com",
        patient_phone="+5511999999999",
        patient_name="João Silva",
        doctor_name="Dr. Maria Santos",
        appointment_datetime=datetime.now() + timedelta(days=1),
        clinic_name="Clínica Prontivus"
    )
    print(result)

asyncio.run(test_reminder())
```

---

## 📊 **MONITORING & LOGS**

### **Check Notification Logs:**
```bash
# View backend logs
tail -f backend/logs/app.log | grep "Notification"
```

### **Common Log Messages:**
- ✅ `Email sent successfully via SendGrid to user@example.com`
- ✅ `SMS sent successfully via Twilio to +5511999999999`
- ⚠️ `SendGrid not configured, email not sent`
- ❌ `Failed to send email via SendGrid: API key invalid`

---

## 💰 **COST ESTIMATES**

### **For 1,000 Patients/Month:**

**Scenario 1: Email Only**
- 1,000 appointment confirmations
- 1,000 appointment reminders
- **Total:** 2,000 emails/month
- **Cost:** $0 (SendGrid free tier: 100/day)

**Scenario 2: Email + SMS**
- 1,000 emails (confirmations)
- 1,000 SMS (reminders)
- **Email Cost:** $0 (SendGrid free tier)
- **SMS Cost:** $25-45/month (Twilio)
- **Total:** $25-45/month

**Scenario 3: High Volume (10,000 patients/month)**
- 10,000 emails
- 10,000 SMS
- **Email Cost:** $0-10/month (SendGrid)
- **SMS Cost:** $250-450/month (Twilio)
- **Total:** $250-460/month

---

## 🔒 **SECURITY BEST PRACTICES**

1. **Never commit API keys to Git**
   - Use environment variables only
   - Add `.env` to `.gitignore`

2. **Rotate API keys regularly**
   - Change keys every 90 days
   - Use different keys for dev/staging/production

3. **Monitor usage**
   - Set up billing alerts in SendGrid/Twilio/AWS
   - Watch for unusual spikes (potential abuse)

4. **Rate limiting**
   - SendGrid: 100 emails/day (free tier)
   - Twilio: No hard limit, but rate limits apply
   - AWS: Varies by region

---

## 🐛 **TROUBLESHOOTING**

### **Problem: Emails not being sent**

**Check:**
1. Is `EMAIL_PROVIDER` set correctly?
2. Is `SENDGRID_API_KEY` valid?
3. Is `EMAIL_FROM` verified in SendGrid?
4. Check backend logs for error messages

**Solution:**
```bash
# Test in Python console
python
>>> from app.services.notification_service import notification_service
>>> import asyncio
>>> asyncio.run(notification_service.send_email("test@example.com", "Test", "Hello"))
```

---

### **Problem: SMS not being sent**

**Check:**
1. Is `SMS_PROVIDER` set correctly?
2. Are Twilio credentials valid?
3. Is phone number in E.164 format (+5511999999999)?
4. Does Twilio account have credit?

**Solution:**
- Check Twilio Console → Logs → SMS Logs
- Verify phone number format
- Add country code (+55 for Brazil)

---

### **Problem: "sendgrid library not installed"**

**Solution:**
```bash
cd backend
pip install sendgrid
pip freeze > requirements.txt
```

---

### **Problem: "twilio library not installed"**

**Solution:**
```bash
cd backend
pip install twilio
pip freeze > requirements.txt
```

---

## 🆘 **SUPPORT**

**Official Documentation:**
- SendGrid: https://docs.sendgrid.com
- Twilio: https://www.twilio.com/docs
- AWS SES: https://docs.aws.amazon.com/ses
- AWS SNS: https://docs.aws.amazon.com/sns

**Brazilian SMS Providers:**
- Zenvia: https://zenvia.com/documentacao
- Total Voice: https://api.totalvoice.com.br/doc

---

## 📝 **NEXT STEPS**

1. ✅ Choose email provider (SendGrid recommended)
2. ✅ Choose SMS provider (Twilio for global, AWS SNS for Brazil)
3. ✅ Set up accounts and get API keys
4. ✅ Add environment variables to Render
5. ✅ Test notifications
6. ✅ Monitor usage and costs
7. ⚠️ Set up WhatsApp Business API (future, for Brazilian market)

---

**Last Updated:** October 11, 2025  
**Version:** 1.0

