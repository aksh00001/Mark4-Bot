Set WshShell = WScript.CreateObject("WScript.Shell")
' Wake the screen
WshShell.SendKeys "{SCROLLLOCK}"
WScript.Sleep 500
WshShell.SendKeys "{SCROLLLOCK}"
WScript.Sleep 500
' Clear the lock image
WshShell.SendKeys "{ESC}"
WScript.Sleep 1000
' Type the PIN (passed as argument)
If WScript.Arguments.Count > 0 Then
    WshShell.SendKeys WScript.Arguments(0)
    WScript.Sleep 500
    WshShell.SendKeys "{ENTER}"
End If
