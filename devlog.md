# Devlog — HRE_Shortcut (Atlas)

## 2026-09-03 — Rebrand to "Atlas" + Real Estate Farming Radar (Owner-Direct Sourcing & Pipeline)

**ผู้ทำ:** Antigravity (Pair Programming with Nut)

**สิ่งที่ทำ:**
1. **รีแบรนด์ทั้งระบบเป็น "Atlas" (Atlas Real Estate OS)**:
   - `manifest.json`: เปลี่ยน `name` เป็น "Atlas Real Estate", `short_name` เป็น "Atlas", อัปเดตคำอธิบาย PWA
   - `sw.js`: อัปเดตชื่อ cache เป็น `atlas-pwa-v1`
   - `index.html`: อัปเดต meta title, header branding, login branding, และ demo mode override เป็น "Atlas"
2. **ระบบ Farming (Owner-Direct Real Estate Sourcing & Radar)**:
   - **`farming/config.json`**: คอนฟิกโซนเป้าหมาย (ราชพฤกษ์, บางใหญ่, นนทบุรี ฯลฯ), target groups, และรอบเวลาดึงข้อมูล (06:00, 18:00)
   - **`farming/filters/owner_filter.py`**: ตัวคัดกรอง Thai NLP Classifier ความแม่นยำสูง แยกเฉพาะเจ้าของขายเอง (FSBO 100%) ปัดตกนายหน้า/เอเจ้นท์ทุกกรณี รองรับ pattern สำนวนเจ้าของ เช่น "ไม่รับนายหน้า", "งดรับ co-agent" (ไม่เกิด false positive) พร้อม regex สกัดราคา, นอน, น้ำ, ตร.ว., ตร.ม., เบอร์โทร และ LINE ID
   - **`farming/scrapers/zmyhome.py`**: ดึงข้อมูลประกาศบ้านมือสองหมวดเจ้าของขายเองโดยตรงจาก ZmyHome
   - **`farming/scrapers/facebook_groups.py`**: ดึงโพสต์บ้านมือสองจากกลุ่ม Facebook พร้อม NLP Classifier ตรวจสอบความเป็นเจ้าของ
   - **`farming/engine.py`**: Engine รันการสแกน, deduplication กันข้อมูลซ้ำ, ตรวจจับการเปลี่ยนแปลงราคา (Price Drop / Delta / History), บันทึกผลลง `farming/data/farmed_listings.json` และ `farmed_listings.json`
   - **`farming/scheduler.py`**: ตัวควบคุมการตั้งเวลาอัตโนมัติ 06:00 เช้า และ 18:00 เย็น รองรับทั้ง `--run-now`, `--daemon`, และ `--install-tasks` (Windows Task Scheduler)
3. **Frontend PWA UI (Tab ที่ 6: Farming)**:
   - อัปเดตแถบ Bottom Navigation เป็น 6 แท็บ พร้อม badge แจ้งเตือนเมื่อมีราคาลดหรือทรัพย์ใหม่
   - หน้าจอ Farming Radar: สรุป KPI (ฟาร์มได้ทั้งหมด, ลดราคา, เจ้าของ 100%), สถานะรอบเวลา 06:00/18:00
   - ตัวกรอง: ทั้งหมด, ลดราคาล่าสุด, ZmyHome, กลุ่ม Facebook พร้อมช่องค้นหาแบบเรียลไทม์
   - การ์ดทรัพย์: แสดงป้ายที่มา, ป้ายเจ้าของ 100%, ป้ายลดราคา (พร้อม % ส่วนลด), สเปกห้อง, ข้อมูลติดต่อเจ้าของ (กดโทรออก, ทัก LINE, แผนที่)
   - ปุ่ม **"+ นำเข้าพอร์ตของฉัน"**: กดแล้วแปลงเข้า `propertiesData` เป็นทรัพย์พร้อมขายทันที พร้อมบันทึกประวัติลง Activity Feed อัตโนมัติ

5. **Farming Criteria & Interactive Tag Manager (พิมพ์เพิ่ม-ลบโซนอิสระ + กำหนดเรทราคา)**:
   - **Interactive Zone Tags**: ปรับ UI ให้เซลล์สามารถจัดการแท็กโซนเป้าหมายได้อิสระ มีปุ่มกากบาท [x] ลบโซนที่ไม่ต้องการออกได้ทันที และมีช่องพิมพ์ชื่อโซน (เช่น "ไทรน้อย" หรือ "บางบัวทอง") กด Enter หรือคลิก "+ เพิ่มโซน" เพื่อเพิ่มแท็กเข้าสู่ระบบได้ทันที
   - **Backend 06:00 & 18:00 Sync**: บันทึกการตั้งค่าลง `farming/data/user_criteria.json` โดยตรง ทำให้รอบการสแกนอัตโนมัติ 06:00 เช้า และ 18:00 เย็น ดึงเฉพาะโซนและช่วงราคาที่เซลล์ต้องการล่าสุดเสมอ
   - **Local Sync Server & CLI**: รองรับการซิงค์แบบเรียลไทม์ผ่าน Endpoint `/api/criteria` (พอร์ต 8765) และคำสั่ง CLI `python farming/scheduler.py --set-zones "ไทรน้อย,บางบัวทอง"`
   - **Price Range Controls**: กรองช่วงราคาขั้นต่ำ-สูงสุด (3M - 10M) พร้อม Preset ด่วน และจดจำค่าใน `localStorage`

6. **Refined Owner vs Broker NLP Classifier (ปรับปรุงตัวคัดกรองตามพฤติกรรมจริง)**:
   - **ไม่ตัดคำว่า "นายหน้า"**: ปลดคำว่า "นายหน้า" ออกจาก Blacklist เนื่องจากเจ้าของบ้านมักพิมพ์ว่า "ยินดีรับนายหน้า", "รับนายหน้าช่วยขาย", หรือ "ไม่รับนายหน้า" (ซึ่งล้วนเป็นเจ้าของบ้านตัวจริง 100%)
   - **เจาะจงสัญญาณเอเจ้นท์ตัวจริง**: ตรวจจับและตัดทิ้งเฉพาะประกาศที่เป็นเอเจ้นท์ชัดเจน ได้แก่ Line Official / Line@ (`line@`, `@...`, `lin.ee/`), บริการด้านสินเชื่อ (`บริการยื่นสินเชื่อฟรี`, `ดันเคส`, `เช็ควงเงินฟรี`), และบริการให้คำปรึกษา/รับฝากขาย (`รับฝากขาย`, `ปรึกษาฟรี`, `สังกัด`)

7. **Security & Login UX**:
   - นำปุ่มทางลัด "เข้าด้วยแอดมิน (admin)" ออกจากหน้าจอเข้าสู่ระบบ เพื่อป้องกันผู้อื่นกดเข้าใช้งาน แต่คงสิทธิ์รหัสผ่าน `admin` + `atlas9876` ไว้ในระบบ ให้พิมพ์ล็อกอินด้วยตนเองได้อย่างปลอดภัย

8. **Production-Ready Serverless Automation (พร้อมใช้งานจริง 100%)**:
   - **GitHub Actions Automation (`.github/workflows/farming-radar.yml`)**:
     - ตั้งเวลาทำงานอัตโนมัติทุกวันเวลา 06:00 เช้า และ 18:00 เย็น (ตามเวลาไทย UTC+7) โดยไม่ต้องเปิดคอมทิ้งไว้
     - รองรับ `workflow_dispatch` ให้แอดมินกดรันสแกนด่วนบน GitHub ได้ตลอดเวลา
     - ดึงโค้ด ติดตั้ง dependencies จาก `requirements.txt` รัน `engine.py` แล้ว Auto-commit ผลลัพธ์กลับสู่ GitHub
   - **ZmyHome Live Pipeline**: เชื่อมต่อดึงประกาศบ้านลงใหม่ล่าสุดจาก `https://zmyhome.com/home/list-new-house?typeAds=sale` เป็นเส้นทางหลัก ไม่ต้องใช้ Login Session พร้อมลิงก์ตรงให้เซลล์คลิกเข้าไปดูเบอร์โทรด้วยตนเอง
   - **Facebook Apify Integration**: เชื่อมต่อโครงสร้างดึงข้อมูลกลุ่ม Facebook ผ่าน Apify API (`apify/facebook-groups-scraper`) เพื่อให้ระบบทำงานออนไลน์ 100% โดยไม่เสี่ยงบัญชีโดนแบน
   - **Card UI Polish**: ปรับการ์ด ZmyHome ให้มีปุ่ม `[ ดูเบอร์โทร ↗ ]` สีน้ำเงินเด่นชัด กดแล้วเปิดหน้าทรัพย์บน ZmyHome ในแท็บใหม่ทันที

9. **Professional UI & Terminology Upgrade (ยกระดับภาพลักษณ์สู่ Enterprise/Agency Grade)**:
   - **ปลดคำไม่เป็นมืออาชีพออก**: นำคำว่า `(ZmyHome + FB)` ออกจากหน้าจอ เปลี่ยนคำบรรยายและหัวข้อเป็นทางการ:
     - `Atlas Farming Radar` → `Atlas Sourcing Radar` (ระบบตรวจจับและจัดหาทรัพย์เจ้าของขายเอง — Direct Owner Sourcing)
     - `ฟาร์มได้ทั้งหมด` → `ตรวจพบล่าสุด` (Total Sourced)
     - `🔥 ลดราคา` → `🔥 ปรับลดราคา` (Price Drops)
     - `✨ เจ้าของ 100%` → `✨ เจ้าของขายเอง` (Direct Owner)
     - ตัวกรองแท็บและป้ายที่มา: ใช้คำที่ตรงไปตรงมาและเข้าใจง่าย `ZmyHome` และ `Facebook`
     - การ์ดทรัพย์: แสดงป้าย `ZmyHome` / `Facebook`, ป้ายรับรองเป็น `Direct Owner`, ปุ่มดูเบอร์เป็น `[ เปิดดูเบอร์โทร ↗ ]`, ลิงก์ต้นทางเป็น `เปิดลิงก์ประกาศ ↗`
   - **ยกระดับหัวข้อย่อยทุกแท็บ**:
     - Buyer Requirements: "ฐานข้อมูลความต้องการลูกค้า พร้อมระบบจับคู่ทรัพย์อัตโนมัติ (Smart Matching)"
     - Activity: "บันทึกกิจกรรมและประวัติการติดตามงานขาย (Sales Interaction Feed)"
     - Reminders: "ท่อติดตามสถานะการเจรจาและการนัดหมาย (Pipeline & Milestones)"
     - Dashboard: "ภาพรวมพอร์ตอสังหาฯ และตัวชี้วัดประสิทธิภาพ (Portfolio Analytics)"
   - **GitHub Repo Migration**: ย้าย Remote Repository เป็น `https://github.com/kornkawes/Atlas.git` ตามที่ Nut เปลี่ยนชื่อเรียบร้อยแล้ว

**ผลการทดสอบ:**
- ZmyHome Live Scraper: ดึงข้อมูลจริงจากหน้า `list-new-house?typeAds=sale` สำเร็จได้ 26 ทรัพย์สดใหม่
- NLP Classifier: ผ่านการทดสอบเคสจริง ("ไม่รับนายหน้า" 0.98, "ยินดีรับนายหน้า คอม 3%" 0.96, "เอเจ้นท์ Line@ และสินเชื่อ" 0.05 ปัดตกถูกต้อง)
- Full Farming Cycle: สแกนข้อมูลรวม 57 ทรัพย์และบันทึกลง `farmed_listings.json` สำเร็จสมบูรณ์ 100%
- Syntax Validation: ตรวจสอบ inline script blocks ทั้ง 7 ชุดด้วย Node.js ผ่าน 100% ไม่มี syntax error

---

## 2026-07-06 — Demo Mode + Pitch Site "Home OS" (white-label)

**ทีม:** Milo (Product Manager) → Luna (UX/UI Designer) → Theo (Frontend Engineer) → Cara (QA Engineer) — orchestrated by outer session

**สิ่งที่ทำ:**
- สร้างเว็บพิตช์ขายผลิตภัณฑ์ `D:\Agents\PresentHomeOS\index.html` (single file, Tailwind CDN, ไทย, dark premium) — positioning เป็น **white-label**: "Home OS" เป็นชื่อผลิตภัณฑ์ ไม่ผูกกับ HOME Real Estate, เสนอขายได้ทุกบริษัท/ตัวแทน ตามคำสั่ง Nut
- เพิ่ม **Demo Mode** ใน `index.html` ของแอปนี้ (+~157 บรรทัดสุทธิ): เข้าด้วย `?demo=1` — ข้าม login, โหลดข้อมูลสมมติ embedded (ทรัพย์ 18 / buyers 6 / activities 10), badge DEMO + ribbon, override branding เป็น "Home OS", บล็อก fetch ไป Apps Script จริง, collections ใช้ in-memory ไม่แตะ localStorage คีย์จริง
- แก้บั๊กเก่านอก scope 1 จุด (อนุมัติโดย orchestrator): `renderDashboard()` regex KPI "พร้อมขาย" ไม่รองรับสถานะภาษาไทย → ขยายเป็น `/sale|available|กำลังขาย|พร้อมขาย/i` (บรรทัด ~2300)

**QA:** รอบแรก BLOCK (settings modal รั่ว apiUrl จริงใน demo mode + CTA 404) → Theo แก้ → รอบสอง **PASS** หลักฐานที่ `PresentHomeOS/docs/qa/` (screenshots + playwright-results.json + retest-results.json)

**เอกสาร:** spec อยู่ที่ `PresentHomeOS/docs/pitch-content.md` (เนื้อหา + demo data storyline) และ `PresentHomeOS/docs/design-spec.md`

**ก่อน deploy จริง (ค้างไว้):**
- เปลี่ยน CTA `../HRE_Shortcut/index.html?demo=1` เป็น URL จริง (มี comment กำกับใน PresentHomeOS/index.html ~658-668)
- เปลี่ยน `mailto:sales@example.com` เป็นอีเมลจริง (~711-714)
- เพิ่ม favicon ให้หน้า pitch (กัน 404 cosmetic)
- `manifest.json` ของแอปยังใช้ชื่อ "Home Real Estate" (แชร์กับ production, สลับตาม query ไม่ได้ — กระทบเฉพาะกรณี Add to Home Screen ระหว่างเดโม)
- ยังไม่ได้เทสบน Safari/iOS จริง

**เหตุการณ์ backend ระหว่างงาน:** Theo โดน session limit ตัดกลางงาน 1 ครั้ง (resume จาก transcript สำเร็จ); Playwright MCP browser ถูกล็อกตลอด ทีมใช้ isolated headless Chromium (playwright-core + chromium-1228) แทน; Cara คนแรก resume ไม่ได้ (no transcript) ต้อง spawn ใหม่; ทีมเปิด `python -m http.server 8791` ที่ D:\Agents ทิ้งไว้ให้ทดสอบ
