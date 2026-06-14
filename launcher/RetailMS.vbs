' RetailMS.vbs — Hidden launcher for Retail Management System
' Double-click this file (or a shortcut to it) to launch the app.
'
' It runs launch.bat in a hidden terminal window.
'
' To create a desktop shortcut, run setup.bat once.

Dim shell, fso, scriptPath, batPath

Set shell = WScript.CreateObject("WScript.Shell")
Set fso = WScript.CreateObject("Scripting.FileSystemObject")

' Resolve the path to launch.bat relative to this VBS file
scriptPath = WScript.ScriptFullName
batPath = Left(scriptPath, InStrRev(scriptPath, "\")) & "launch.bat"

If Not fso.FileExists(batPath) Then
    MsgBox "Error: launch.bat not found at " & batPath & vbCrLf & vbCrLf & _
           "Make sure launch.bat is in the same folder as this file.", _
           vbCritical, "RetailMS — Launch Error"
    WScript.Quit 1
End If

' Run launch.bat hidden, fire and forget
shell.Run """" & batPath & """", 0, False

Set shell = Nothing
Set fso = Nothing
