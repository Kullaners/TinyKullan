#Requires AutoHotkey v2.0
#SingleInstance Off
SendMode "Input"
SetWorkingDir A_ScriptDir

OnExit(ReleaseAllHeld)

; Track held mouse buttons for proper cleanup
Global HeldLeft := False
Global HeldRight := False
Global HeldMiddle := False

; Global Variables
Global Recording := False
Global Playing := False
Global Events := []
Global StartTime := 0
Global LastX := 0
Global LastY := 0
Global LoopPlayback := False
Global Mode := ""
Global MacroPath := ""
Global KeyHook := ""
Global StopPath := ""
Global WindowsMouseHook := 0
Global SpeedMultiplier := 1.0
Global LastPressTimes := Map()  ; filter OS auto-repeat keys during recording

; Command line argument parsing
Global ImgClickX := 0
Global ImgClickY := 0
for index, arg in A_Args {
    if (arg = "/play" and index + 1 <= A_Args.Length) {
        Mode := "Play"
        MacroPath := A_Args[index + 1]
    } else if (arg = "/loop") {
        LoopPlayback := True
    } else if (arg = "/speed" and index + 1 <= A_Args.Length) {
        SpeedMultiplier := Max(0.1, Float(A_Args[index + 1]))
    } else if (arg = "/record" and index + 1 <= A_Args.Length) {
        Mode := "Record"
        MacroPath := A_Args[index + 1]
        StopPath := MacroPath ".stop"
    } else if (arg = "/imgclick" and index + 2 <= A_Args.Length) {
        Mode := "ImgClick"
        ImgClickX := Integer(A_Args[index + 1])
        ImgClickY := Integer(A_Args[index + 2])
    } else if (arg = "/worker") {
        Mode := "Worker"
    }
}

If (Mode = "Play") {
    LoadMacroFile(MacroPath)
    Playing := True
    PlayWorker()
    ExitApp()
} Else if (Mode = "Record") {
    StartRecording()
    Return
} Else if (Mode = "ImgClick") {
    ; Use Event mode (mouse_event API) — Roblox accepts this unlike SendInput
    SendMode("Event")
    CoordMode("Mouse", "Screen")
    ; Activate Roblox so the click lands on it
    if WinExist("ahk_exe RobloxPlayerBeta.exe") {
        WinActivate("ahk_exe RobloxPlayerBeta.exe")
        WinWaitActive("ahk_exe RobloxPlayerBeta.exe",, 1)
    }
    MouseMove(ImgClickX, ImgClickY, 0)
    Sleep(50)
    Click("down")
    Sleep(50)
    Click("up")
    ExitApp()
} Else if (Mode = "Worker") {
    SendMode("Event")
    CoordMode("Mouse", "Screen")
    Loop {
        signalPath := A_Temp "\TinyKullan_ahk_cmd.txt"
        if FileExist(signalPath) {
            try {
                cmdLine := FileRead(signalPath)
                FileDelete(signalPath)
                cmdLine := Trim(cmdLine)
                if (cmdLine = "exit") {
                    ExitApp
                }
                if SubStr(cmdLine, 1, 5) = "click" {
                    parts := StrSplit(cmdLine, " ")
                    if parts.Length >= 3 {
                        MouseMove(Integer(parts[2]), Integer(parts[3]), 0)
                        Sleep(30)
                        Click("down")
                        Sleep(30)
                        Click("up")
                    }
                }
            } catch {
                Sleep(500)
            }
        }
        Sleep(50)
    }
}

; UI Creation (Standalone mode)
MyGui := Gui("+AlwaysOnTop -MaximizeBox", "TinyKullan AHK")
MyGui.BackColor := "1E1E24"
MyGui.SetFont("s10 Bold Q5", "Segoe UI")
StatusText := MyGui.AddText("x10 y12 w280 cFFFFFF vStatus", "Ready")

MyGui.SetFont("s9 Norm Q5", "Segoe UI")
BtnRecord := MyGui.AddButton("x10 y45 w85 h30 vBtnRecord", "Record (F5)")
BtnPlay := MyGui.AddButton("x105 y45 w85 h30 vBtnPlay", "Play (F6)")
BtnClear := MyGui.AddButton("x200 y45 w80 h30", "Clear")
LoopCheckbox := MyGui.AddCheckbox("x15 y85 w260 cFFFFFF vLoopCheckbox", "Loop Playback")

BtnRecord.OnEvent("Click", (*) => ToggleRecord())
BtnPlay.OnEvent("Click", (*) => TogglePlay())
BtnClear.OnEvent("Click", (*) => ClearEvents())
LoopCheckbox.OnEvent("Click", (*) => ToggleLoop())

MyGui.OnEvent("Close", (*) => ExitApp())
MyGui.Show("w290 h115")
Return


ToggleLoop() {
    Global LoopPlayback, MyGui
    saved := MyGui.Submit(False)
    LoopPlayback := saved.LoopCheckbox
}

ToggleRecord() {
    Global Playing, Recording, Mode, MacroPath
    if (Playing)
        Return
    if (Recording) {
        StopRecording()
        if (Mode = "Record") {
            SaveMacroFile(MacroPath)
            ExitApp()
        }
    } else {
        StartRecording()
    }
}

TogglePlay() {
    Global Recording, Playing
    if (Recording)
        Return
    if (Playing) {
        StopPlayback()
    } else {
        StartPlayback()
    }
}

StartRecording() {
    Global Recording, Events, StartTime, LastX, LastY, MyGui, Mode, StopPath, WindowsMouseHook
    Recording := True
    Events := []

    if (Mode = "") {
        MyGui["Status"].Value := "Recording... (F5 to Stop)"
        MyGui["BtnPlay"].Enabled := False
        MyGui["BtnRecord"].Text := "Stop (F5)"
    }

    pt := Buffer(8, 0)
    DllCall("GetCursorPos", "Ptr", pt)
    LastX := NumGet(pt, 0, "Int")
    LastY := NumGet(pt, 4, "Int")

    StartTime := QPC()

    ; Record the baseline starting position
    Events.Push({t: "M", d: 0, x: LastX, y: LastY})

    ; Start the Low-Level Windows Mouse Hook (WH_MOUSE_LL = 14)
    WindowsMouseHook := DllCall("SetWindowsHookEx", "Int", 14, "Ptr", CallbackCreate(LowLevelMouseProc, "Fast"), "Ptr", DllCall("GetModuleHandle", "Ptr", 0, "Ptr"), "UInt", 0, "Ptr")

    if (!WindowsMouseHook) {
        MsgBox "Mouse hook failed to install. Try running as Administrator.", "TinyKullan", "Icon!"
        ExitApp
    }

    if (Mode = "Record" && StopPath != "")
        SetTimer(CheckStopSignal, 50)
    StartKeyboardHook()
}

StopRecording() {
    Global Recording, MyGui, Mode, WindowsMouseHook
    Recording := False

    ; Unhook the Windows mouse hook safely
    if (WindowsMouseHook) {
        DllCall("UnhookWindowsHookEx", "Ptr", WindowsMouseHook)
        WindowsMouseHook := 0
    }

    SetTimer(CheckStopSignal, 0)
    StopKeyboardHook()

    if (Mode = "") {
        MyGui["BtnPlay"].Enabled := True
        MyGui["BtnRecord"].Text := "Record (F5)"
        MyGui["Status"].Value := "Finished Recording"
    }
}

CheckStopSignal() {
    Global Recording, StopPath, MacroPath
    if (!Recording || StopPath = "")
        Return
    if (FileExist(StopPath)) {
        try {
            FileDelete(StopPath)
        } catch {
        }
        StopRecording()
        SaveMacroFile(MacroPath)
        ExitApp()
    }
}

ClearEvents() {
    Global Recording, Playing, Events, MyGui, Mode
    if (Recording || Playing)
        Return
    Events := []
    if (Mode = "")
        MyGui["Status"].Value := "Cleared Macro"
}

LowLevelMouseProc(nCode, wParam, lParam) {
    Global Recording, Events, StartTime, LastX, LastY

    if (nCode >= 0 && wParam = 0x0200 && Recording) {
        ; Offset 12 contains the flags field.
        ; bit 0 (0x01) = LLMHF_INJECTED (programmatic events like SetCursorPos or SendInput)
        flags := NumGet(lParam, 12, "UInt")

        if (!(flags & 1)) { ; ONLY process genuine hardware mouse movements
            x := NumGet(lParam, 0, "Int")
            y := NumGet(lParam, 4, "Int")

            if (x != LastX || y != LastY) {
                ; Only record moves > 3px to avoid jitter spam during playback
                if (Abs(x - LastX) > 3 || Abs(y - LastY) > 3) {
                    delay := Round(QPC() - StartTime)
                    Events.Push({t: "M", d: delay, x: x, y: y})
                    LastX := x
                    LastY := y
                }
            }
        }
    }
    ; Pass the event along to other applications/hooks
    Return DllCall("CallNextHookEx", "Ptr", 0, "Int", nCode, "Ptr", wParam, "Ptr", lParam, "Ptr")
}

RecordClick(btn, state) {
    Global Recording, Events, StartTime
    if (!Recording)
        Return
    delay := Round(QPC() - StartTime)
    pt := Buffer(8, 0)
    DllCall("GetCursorPos", "Ptr", pt)
    x := NumGet(pt, 0, "Int")
    y := NumGet(pt, 4, "Int")
    Events.Push({t: "C", d: delay, b: btn, s: state, x: x, y: y})
}


; Keyboard Hook (Using InputHook)
StartKeyboardHook() {
    Global KeyHook
    KeyHook := InputHook("V L0")
    KeyHook.KeyOpt("{All}", "N")
    KeyHook.OnKeyDown := OnKeyPress
    KeyHook.OnKeyUp := OnKeyRelease
    KeyHook.Start()
}

StopKeyboardHook() {
    Global KeyHook
    if (KeyHook)
        KeyHook.Stop()
}

OnKeyPress(ih, vk, sc, extended := 0) {
    Global Recording, Events, StartTime, LastPressTimes
    if (!Recording)
        Return
    if (vk = 0x74 || vk = 0x75 || vk = 0x77)  ; skip F5/F6/F8
        Return

    ; Filter OS auto-repeats: skip if same VK pressed within last 50ms
    now := QPC()
    if LastPressTimes.Has(vk) && (now - LastPressTimes[vk]) < 50
        Return
    LastPressTimes[vk] := now

    delay := Round(QPC() - StartTime)
    Events.Push({t: "K", d: delay, vk: vk, sc: sc, ext: extended, s: "Down"})
}

OnKeyRelease(ih, vk, sc, extended := 0) {
    Global Recording, Events, StartTime
    if (!Recording)
        Return
    if (vk = 0x74 || vk = 0x75 || vk = 0x77)
        Return
    delay := Round(QPC() - StartTime)
    Events.Push({t: "K", d: delay, vk: vk, sc: sc, ext: extended, s: "Up"})
}

; Playback Engine
StartPlayback() {
    Global Playing, Events, LoopPlayback, MyGui, Mode
    if (Events.Length = 0) {
        if (Mode = "")
            MyGui["Status"].Value := "Macro is empty!"
        Return
    }
    Playing := True
    if (Mode = "") {
        MyGui["BtnRecord"].Enabled := False
        MyGui["BtnPlay"].Text := "Stop (F6)"
        MyGui["Status"].Value := "Playing... (F6 to Stop)"
    }
    SetTimer(PlayWorker, -1)
}

StopPlayback() {
    Global Playing, MyGui, Mode
    Playing := False
    if (Mode = "") {
        MyGui["BtnRecord"].Enabled := True
        MyGui["BtnPlay"].Text := "Play (F6)"
        MyGui["Status"].Value := "Stopped Playback"
    }
    ReleaseAllHeld(0)
}

PlayWorker() {
    Global Playing, Events, LoopPlayback, SpeedMultiplier, HeldLeft, HeldRight, HeldMiddle
    Loop {
        if (!Playing)
            Break

        startTimePlay := QPC()
        eventCount := Events.Length

        Loop eventCount {
            if (!Playing)
                Break

            ev := Events[A_Index]
            targetTime := ev.d / SpeedMultiplier

            Loop {
                if (!Playing)
                    Break
                elapsed := QPC() - startTimePlay
                remaining := targetTime - elapsed
                if (remaining <= 0) {
                    Break
                }
                if (remaining > 15) {
                    Sleep(10)
                } else if (remaining > 2) {
                    DllCall("Sleep", "UInt", 1)
                }
            }

            t := ev.t
            if (t = "M") {
                ; ALWAYS use relative movement — never teleport with SetCursorPos
                pt := Buffer(8, 0)
                DllCall("GetCursorPos", "Ptr", pt)
                currX := NumGet(pt, 0, "Int")
                currY := NumGet(pt, 4, "Int")
                dx := ev.x - currX
                dy := ev.y - currY
                if (dx != 0 || dy != 0) {
                    SendMouseInput(dx, dy, 0x0001)
                }
            } else if (t = "C") {
                ; Use absolute positioning — bypasses mouse acceleration that
                ; would cause large relative moves to drift.
                SendMouseAbsolute(ev.x, ev.y)
                Sleep(10)
                btn := ev.b
                state := ev.s
                dwFlags := 0
                if (btn = "left") {
                    dwFlags := (state = "Down") ? 0x0002 : 0x0004
                } else if (btn = "right") {
                    dwFlags := (state = "Down") ? 0x0008 : 0x0010
                } else if (btn = "middle") {
                    dwFlags := (state = "Down") ? 0x0020 : 0x0040
                }
                SendMouseInput(0, 0, dwFlags)
                if (btn = "left")
                    HeldLeft := (state = "Down")
                else if (btn = "right")
                    HeldRight := (state = "Down")
                else if (btn = "middle")
                    HeldMiddle := (state = "Down")
            } else if (t = "K") {
                SendKeyInput(ev.vk, ev.sc, ev.s = "Up")
            } else if (t = "W") {
                ; Move relatively to wheel target, then scroll
                pt := Buffer(8, 0)
                DllCall("GetCursorPos", "Ptr", pt)
                currX := NumGet(pt, 0, "Int")
                currY := NumGet(pt, 4, "Int")
                dx := ev.x - currX
                dy := ev.y - currY
                if (dx != 0 || dy != 0) {
                    SendMouseInput(dx, dy, 0x0001)
                }
                SendMouseWheelInput(ev.delta, 0x0800)
            } else if (t = "B") {
                ; Branch/if-image — AHK cannot do image detection, skip unconditionally
            }
        }

        if (!LoopPlayback || !Playing) {
            StopPlayback()
            Break
        }
    }
}

IsCursorLocked() {
    hwnd := DllCall("GetForegroundWindow", "Ptr")
    if (!hwnd)
        Return False

    ; Check if ClipCursor has constrained the cursor to a tiny rect (game lock)
    clipRect := Buffer(16, 0)
    DllCall("GetClipCursor", "Ptr", clipRect)
    clipW := NumGet(clipRect, 8, "Int") - NumGet(clipRect, 0, "Int")
    clipH := NumGet(clipRect, 12, "Int") - NumGet(clipRect, 4, "Int")
    if (clipW < 10 && clipH < 10)
        Return True

    rect := Buffer(16, 0)
    if (DllCall("GetClientRect", "Ptr", hwnd, "Ptr", rect)) {
        ptCenter := Buffer(8, 0)
        cx := NumGet(rect, 8, "Int") // 2
        cy := NumGet(rect, 12, "Int") // 2
        NumPut("Int", cx, ptCenter, 0)
        NumPut("Int", cy, ptCenter, 4)
        DllCall("ClientToScreen", "Ptr", hwnd, "Ptr", ptCenter)
        centerX := NumGet(ptCenter, 0, "Int")
        centerY := NumGet(ptCenter, 4, "Int")

        ptCurr := Buffer(8, 0)
        DllCall("GetCursorPos", "Ptr", ptCurr)
        currX := NumGet(ptCurr, 0, "Int")
        currY := NumGet(ptCurr, 4, "Int")

        if (Abs(currX - centerX) <= 2 && Abs(currY - centerY) <= 2) {
            Return True
        }
    }
    Return False
}

SendMouseInput(dx, dy, dwFlags) {
    input := Buffer(40, 0)
    NumPut("UInt", 0, input, 0)
    NumPut("Int", dx, input, 8)
    NumPut("Int", dy, input, 12)
    NumPut("UInt", 0, input, 16)
    NumPut("UInt", dwFlags, input, 20)
    NumPut("UInt", 0, input, 24)
    NumPut("UPtr", 0, input, 32)
    DllCall("SendInput", "UInt", 1, "Ptr", input, "Int", 40)
}

SendMouseAbsolute(screenX, screenY) {
    ; Move to absolute screen coordinates on the virtual desktop.
    ; Identical logic to Python's _abs() — accounts for multi-monitor
    ; offsets and bypasses mouse acceleration entirely.
    static vScreenX := 0, vScreenY := 0, vScreenW := 0, vScreenH := 0
    if (!vScreenW) {
        vScreenX := DllCall("GetSystemMetrics", "Int", 76)  ; SM_XVIRTUALSCREEN
        vScreenY := DllCall("GetSystemMetrics", "Int", 77)  ; SM_YVIRTUALSCREEN
        vScreenW := DllCall("GetSystemMetrics", "Int", 78)  ; SM_CXVIRTUALSCREEN
        vScreenH := DllCall("GetSystemMetrics", "Int", 79)  ; SM_CYVIRTUALSCREEN
        if (!vScreenW || !vScreenH) {
            vScreenW := DllCall("GetSystemMetrics", "Int", 0)  ; SM_CXSCREEN
            vScreenH := DllCall("GetSystemMetrics", "Int", 1)  ; SM_CYSCREEN
            vScreenX := 0
            vScreenY := 0
        }
    }
    ax := Round((screenX - vScreenX) * 65535 / Max(vScreenW - 1, 1))
    ay := Round((screenY - vScreenY) * 65535 / Max(vScreenH - 1, 1))
    input := Buffer(40, 0)
    NumPut("UInt", 0, input, 0)                      ; type = INPUT_MOUSE
    NumPut("Int", ax, input, 8)                       ; dx (normalized 0-65535)
    NumPut("Int", ay, input, 12)                      ; dy (normalized 0-65535)
    NumPut("UInt", 0, input, 16)                     ; mouseData
    NumPut("UInt", 0xC001, input, 20)                ; ABSOLUTE | VIRTUALDESKTOP | MOVE
    NumPut("UInt", 0, input, 24)                     ; time
    NumPut("UPtr", 0, input, 32)                     ; dwExtraInfo
    DllCall("SendInput", "UInt", 1, "Ptr", input, "Int", 40)
}

SendKeyInput(vk, sc, up) {
    input := Buffer(40, 0)
    NumPut("UInt", 1, input, 0)
    NumPut("UShort", vk, input, 8)
    NumPut("UShort", sc, input, 10)

    dwFlags := 0x0008
    if (up)
        dwFlags |= 0x0002
    ; Extended keys: Right-side modifiers, arrows, nav keys, Win, Apps, Numpad
    if (vk = 0xA3 || vk = 0xA5 || vk = 0xA1  ; Right Ctrl/Alt/Shift
        || vk = 0x5B || vk = 0x5C || vk = 0x5D  ; Win keys + Apps
        || vk = 0x21 || vk = 0x22 || vk = 0x23 || vk = 0x24  ; PgUp/Dn/End/Home
        || vk = 0x25 || vk = 0x26 || vk = 0x27 || vk = 0x28  ; Arrows
        || vk = 0x2D || vk = 0x2E  ; Insert/Delete
        || vk = 0x6F || vk = 0x90)   ; NumpadDiv/NumLock
        dwFlags |= 0x0001

    NumPut("UInt", dwFlags, input, 12)
    NumPut("UInt", 0, input, 16)
    NumPut("UPtr", 0, input, 24)
    DllCall("SendInput", "UInt", 1, "Ptr", input, "Int", 40)
}

SendMouseWheelInput(delta, dwFlags) {
    ; Position set by caller via SetCursorPos — x,y removed from signature
    input := Buffer(40, 0)
    NumPut("UInt", 0, input, 0)
    NumPut("Int", 0, input, 8)
    NumPut("Int", 0, input, 12)
    NumPut("Int", delta, input, 16)
    NumPut("UInt", dwFlags, input, 20)
    NumPut("UInt", 0, input, 24)
    NumPut("UPtr", 0, input, 32)
    DllCall("SendInput", "UInt", 1, "Ptr", input, "Int", 40)
}

ReleaseAllHeld(exitReason := 0, exitCode := 0) {
    Global Mode, HeldLeft, HeldRight, HeldMiddle
    if (Mode = "ImgClick")
        Return
    ; Release mouse buttons only if held during playback
    if (HeldLeft)
        SendMouseInput(0, 0, 0x0004)
    if (HeldRight)
        SendMouseInput(0, 0, 0x0010)
    if (HeldMiddle)
        SendMouseInput(0, 0, 0x0040)

    ; Aggressively release ALL modifier and action keys via SendInput
    vks := [0x10, 0x11, 0x12, 0x5B, 0x5C,  ; Shift/Ctrl/Alt/LWin/RWin
            0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5,  ; Left/Right variants
            0x57, 0x41, 0x53, 0x44,          ; WASD
            0x25, 0x26, 0x27, 0x28,          ; Arrows
            0x20, 0x0D, 0x1B, 0x09,          ; Space/Enter/Esc/Tab
            0x51, 0x45, 0x52, 0x46,          ; Q/E/R/F
            0x08, 0x2E, 0x14,                ; BS/Del/Caps
            0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77,  ; F1-F8
            0x21, 0x22, 0x23, 0x24, 0x2D, 0x2E]  ; PgUp/Dn/End/Home/Ins/Del
    for idx, vk in vks {
        sc := DllCall("MapVirtualKey", "UInt", vk, "UInt", 0, "UInt")
        SendKeyInput(vk, sc, True)
    }
}

LoadMacroFile(filePath) {
    Global Events
    Events := []
    if (!FileExist(filePath))
        Return

    content := FileRead(filePath)
    absTime := 0
    Loop Parse, content, "`n", "`r"
    {
        if (A_LoopField = "")
            Continue

        fields := StrSplit(A_LoopField, ",")
        if (fields.Length < 10)
            Continue

        ev := {}
        ev.t := fields[1]
        absTime += fields[2] + 0
        ev.d := absTime
        ev.x := fields[3] + 0
        ev.y := fields[4] + 0
        ev.b := fields[5]
        ev.s := (fields[6] = "1" || fields[6] = "Up") ? "Up" : "Down"
        ev.vk := fields[7] + 0
        ev.sc := fields[8] + 0
        ev.ext := fields[9] + 0
        ev.delta := fields[10] + 0

        Events.Push(ev)
    }
}

SaveMacroFile(filePath) {
    Global Events
    if (FileExist(filePath))
        FileDelete(filePath)

    content := ""
    lastTime := 0
    for idx, ev in Events {
        t := HasProp(ev, "t") ? ev.t : ""
        eventTime := HasProp(ev, "d") ? ev.d : lastTime
        d := Max(0, eventTime - lastTime)
        lastTime := eventTime
        x := HasProp(ev, "x") ? ev.x : 0
        y := HasProp(ev, "y") ? ev.y : 0
        btn := HasProp(ev, "b") ? ev.b : ""
        up := (HasProp(ev, "s") && ev.s = "Up") ? 1 : 0
        vk := HasProp(ev, "vk") ? ev.vk : 0
        sc := HasProp(ev, "sc") ? ev.sc : 0
        ext := HasProp(ev, "ext") ? ev.ext : 0
        delta := HasProp(ev, "delta") ? ev.delta : 0

        content .= t "," d "," x "," y "," btn "," up "," vk "," sc "," ext "," delta "`r`n"
    }
    FileAppend(content, filePath)
}

QPC() {
    static freq := 0
    if (!freq)
        DllCall("QueryPerformanceFrequency", "Int64*", &freq)
    DllCall("QueryPerformanceCounter", "Int64*", &count:=0)
    return (count * 1000) / freq
}

; Emergency unlock — press Esc to release ALL stuck modifiers
~Esc:: {
    if (Playing || Recording)
        return  ; let normal Esc pass through during playback/recording
}
^Esc::EmergencyRelease()
+Esc::EmergencyRelease()

EmergencyRelease() {
    Send("{Ctrl up}{Alt up}{Shift up}{LWin up}{RWin up}")
    MsgBox("All modifier keys released.", "TinyKullan — Emergency", "Iconi T2")
}

; Hotkeys
F5::ToggleRecord()
F6::TogglePlay()

~*LButton::RecordClick("left", "Down")
~*LButton Up::RecordClick("left", "Up")
~*RButton::RecordClick("right", "Down")
~*RButton Up::RecordClick("right", "Up")
~*MButton::RecordClick("middle", "Down")
~*MButton Up::RecordClick("middle", "Up")

; Wheel recording (Bug 8 fix)
~*WheelUp::RecordWheel(120)
~*WheelDown::RecordWheel(-120)

RecordWheel(delta) {
    Global Recording, Events, StartTime
    if (!Recording)
        Return
    delay := Round(QPC() - StartTime)
    pt := Buffer(8, 0)
    DllCall("GetCursorPos", "Ptr", pt)
    Events.Push({t: "W", d: delay,
                 x: NumGet(pt, 0, "Int"), y: NumGet(pt, 4, "Int"),
                 delta: delta})
}
