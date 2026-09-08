' VBScript to launch Vision Stream Bridge silently in the background (0 = hidden window)
Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Get current script directory
scriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)

' Command to run Python headless service
command = "py """ & scriptDir & "\service_main.py"""

' Check if pythonw is available to avoid console entirely, else py
objShell.CurrentDirectory = scriptDir
objShell.Run command, 0, False
