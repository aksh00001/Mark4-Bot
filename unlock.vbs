Set WshShell = CreateObject("WScript.Shell")
WshShell.SendKeys "{ESC}"
WScript.Sleep 1000
WshShell.SendKeys "2110"
WScript.Sleep 500
WshShell.SendKeys "{ENTER}"
