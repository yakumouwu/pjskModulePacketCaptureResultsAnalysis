@echo off
setlocal
schtasks /Create /TN "MysekaiAutoCommit" /SC MINUTE /MO 10 /TR "\"D:\reverse\auto_commit.bat\"" /F
echo Task created: MysekaiAutoCommit
echo It will run every 10 minutes.
echo You can also run D:\reverse\auto_commit.bat manually for a one-time sync.
pause
