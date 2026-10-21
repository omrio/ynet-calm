# ynet רגוע

דף חדשות אישי בעברית המבוסס על ערוצי RSS של ynet, ללא ספורט וכותרות קשות. אינו משכפל את דף הבית המקורי של ynet. אין צורך בתוספי דפדפן.

## התקנה ב־GitHub

1. צור מאגר ציבורי בשם `ynet-calm` (לא לסמן Initialize with README).
2. העלה את תוכן התיקייה הזו (כולל תיקיית `.github`) לענף `main`. דרך קלה: גרור קבצים דרך Add file > Upload files, או השתמש ב־git.
3. ב־Settings > Pages > Build and deployment בחר `GitHub Actions`.
4. ב־Actions > Update filtered news and deploy בחר Run workflow להפעלה ראשונה. בכל שעה GitHub Actions ינסה לעדכן את המידע ולפרסם את האתר.
5. הקישור יהיה `https://USERNAME.github.io/ynet-calm/` כאשר USERNAME הוא שם המשתמש שלך ב־GitHub.

**הערות:** GitHub עשוי לעכב הרצות מתוזמנות; עלולות להיות תקלות זמניות בהזנת RSS. המידע מתעדכן רק אם משימת GitHub Actions הצליחה. הסינון פועל בדפדפן בעת הצגת הדף, בלי התקנת קוד מקומי; רשימת המילים האישית נשמרת ב־localStorage של הדפדפן ונבדקת מול כותרות בלבד. התמונה והתקציר נשאבים מערוצי RSS, ולא תמיד יהיו זמינים. שים לב: לא מדובר בסינון סמנטי; ידיעות קשות ללא מילה תואמת עדיין עלולות להופיע.

הערוצים והקישורים מפורסמים על ידי ynet: https://www.ynet.co.il/articles/0,7340,L-3136256,00.html
