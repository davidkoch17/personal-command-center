' ===========================================================================
'  Personal Command Center v3 — silent launcher
'
'  Run by wscript.exe, this script has NO console of its own, so nothing
'  flashes on screen. It:
'    1. Checks http://localhost:8000/health (hidden, via ServerXMLHTTP).
'    2. If the backend is down, starts it WINDOWLESS by reusing the committed
'       _backend_only.bat (resolves pythonw, redirects logs), launched hidden.
'    3. Polls until the backend is healthy (cold start loads finance libs,
'       can take ~30-50s).
'    4. Opens the dashboard in the default browser at the Portfolio Hub
'       (the v3 entry point — Home is archived, Portfolio is the landing page).
'
'  Pass the argument "backendonly" to start the backend without opening a
'  browser — used by the on-login autostart shortcut.
'
'  This replaces .bat-targeted shortcuts, which always flash a console window
'  and spawn visible powershell children (the old command-popup problem).
' ===========================================================================

Option Explicit

Dim sh, fso, scriptDir, backendOnly, arg, i
Set sh  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

backendOnly = False
For Each arg In WScript.Arguments
    If LCase(arg) = "backendonly" Then backendOnly = True
Next

If Not BackendUp() Then
    ' Start the backend hidden (windowStyle 0). _backend_only.bat uses
    ' `start "" /B pythonw ...` so it returns immediately and the backend
    ' keeps running detached. No window ever appears.
    sh.Run """" & scriptDir & "\_backend_only.bat""", 0, True

    ' Wait for readiness — up to ~60s for a cold start.
    For i = 1 To 80
        If BackendUp() Then Exit For
        WScript.Sleep 750
    Next
End If

If Not backendOnly Then
    ' Open the dashboard in the default browser at the Portfolio Hub (no console).
    sh.Run "http://localhost:8000/portfolio", 1, False
End If

' ---------------------------------------------------------------------------
Function BackendUp()
    On Error Resume Next
    Dim http
    Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    http.SetTimeouts 2000, 2000, 2000, 3000
    http.Open "GET", "http://localhost:8000/health", False
    http.Send
    BackendUp = (Err.Number = 0) And (http.Status = 200)
    On Error GoTo 0
End Function
