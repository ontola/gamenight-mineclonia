/* SPDX-License-Identifier: MIT */
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <wchar.h>
int WINAPI wWinMain(HINSTANCE h, HINSTANCE prev, PWSTR tail, int show) {
    wchar_t directory[32768], executable[32768], command[32768];
    DWORD size = GetModuleFileNameW(NULL, directory, 32768);
    if (!size || size >= 32768) return 2;
    wchar_t *end = wcsrchr(directory, L'\\');
    if (!end) return 2;
    *end = 0;
    if (swprintf(executable, 32768, L"%ls\\python\\python.exe", directory) < 0 ||
        swprintf(command, 32768, L"\"%ls\" \"%ls\\adapter\\launch.py\" %ls",
                 executable, directory, tail) < 0) return 2;
    STARTUPINFOW startup = {0};
    PROCESS_INFORMATION process = {0};
    startup.cb = sizeof(startup);
    startup.dwFlags = STARTF_USESHOWWINDOW;
    startup.wShowWindow = SW_HIDE;
    if (!CreateProcessW(executable, command, NULL, NULL, FALSE, CREATE_NO_WINDOW,
                        NULL, directory, &startup, &process)) return 3;
    WaitForSingleObject(process.hProcess, INFINITE);
    DWORD code = 1;
    GetExitCodeProcess(process.hProcess, &code);
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return (int)code;
}
