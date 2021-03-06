import sublime
import sublime_plugin
import os
import sys
import subprocess

if os.name == 'nt':
    import winreg


class NotFoundError(Exception):
    pass


def get_platform_setting(settings, key):
    value = settings.get('%s_%s' % (key, sublime.platform()))
    if not value:
        value = settings.get(key)
    return value


class TerminalSelector():
    default = None

    @staticmethod
    def get():
        settings = sublime.load_settings('Terminal.sublime-settings')
        package_dir = os.path.join(sublime.packages_path(), "Terminal")

        terminal = get_platform_setting(settings, 'terminal')
        if terminal:
            dir, executable = os.path.split(terminal)
            if not dir:
                joined_terminal = os.path.join(package_dir, executable)
                if os.path.exists(joined_terminal):
                    terminal = joined_terminal
                    if not os.access(terminal, os.X_OK):
                        os.chmod(terminal, 0o755)
            return terminal

        if TerminalSelector.default:
            return TerminalSelector.default

        default = None

        if os.name == 'nt':
            if os.path.exists(
                    os.environ['SYSTEMROOT'] +
                    '\\System32\\WindowsPowerShell\\v1.0\\powershell.exe'):
                # This mimics the default powershell colors since calling
                # subprocess.POpen() ends up acting like launching powershell
                # from cmd.exe. Normally the size and color are inherited
                # from cmd.exe, but this creates a custom mapping, and then
                # the LaunchPowerShell.bat file adjusts some other settings.
                key_string = 'Console\\%SystemRoot%_system32_' + \
                    'WindowsPowerShell_v1.0_powershell.exe'
                try:
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                         key_string)
                except (WindowsError):
                    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                           key_string)
                    winreg.SetValueEx(key, 'ColorTable05', 0,
                                      winreg.REG_DWORD, 5645313)
                    winreg.SetValueEx(key, 'ColorTable06', 0,
                                      winreg.REG_DWORD, 15789550)
                default = os.path.join(package_dir, 'PS.bat')
            else:
                default = os.environ['SYSTEMROOT'] + '\\System32\\cmd.exe'

        elif sys.platform == 'darwin':
            default = os.path.join(package_dir, 'Terminal.sh')
            if not os.access(default, os.X_OK):
                os.chmod(default, 0o755)

        else:
            ps = 'ps -eo comm | grep -E "gnome-session|ksmserver|' + \
                'xfce4-session" | grep -v grep'
            wm = [x.replace("\n", '') for x in os.popen(ps)]
            if wm:
                if wm[0] == 'gnome-session':
                    default = 'gnome-terminal'
                elif wm[0] == 'xfce4-session':
                    default = 'terminal'
                elif wm[0] == 'ksmserver':
                    default = 'konsole'
            if not default:
                default = 'xterm'

        TerminalSelector.default = default
        return default


class TerminalCommand():
    def get_path(self, paths):
        if paths:
            return paths[0]
        elif self.window.active_view():
            return self.window.active_view().file_name()
        elif self.window.folders():
            return self.window.folders()[0]
        else:
            sublime.error_message("Terminal" + ': No place to open terminal to')
            return False

    def run_terminal(self, dir, parameters):
        try:
            if not dir:
                raise NotFoundError('The file open in the selected view has ' +
                                    'not yet been saved')
            for k, v in enumerate(parameters):
                parameters[k] = v.replace('%CWD%', dir)
            args = [TerminalSelector.get()]
            args.extend(parameters)
            subprocess.Popen(args, cwd=dir)

        except (OSError) as exception:
            sublime.error_message("Terminal" + ': The terminal ' +
                                  TerminalSelector.get() + ' was not found')
        except (Exception) as exception:
            sublime.error_message("Terminal" + ': ' + str(exception))


class OpenTerminalCommand(sublime_plugin.WindowCommand, TerminalCommand):
    def run(self, paths=[], parameters=None):
        path = self.get_path(paths)
        if not path:
            return

        if parameters is None:
            settings = sublime.load_settings('Terminal.sublime-settings')
            parameters = get_platform_setting(settings, 'parameters')

        if not parameters:
            parameters = []

        if os.path.isfile(path):
            path = os.path.dirname(path)

        self.run_terminal(path, parameters)


class OpenTerminalProjectFolderCommand(sublime_plugin.WindowCommand,
                                       TerminalCommand):
    def run(self, paths=[], parameters=None):
        path = self.get_path(paths)
        if not path:
            return

        folders = [x for x in self.window.folders() if path.find(x) == 0][0:1]

        command = OpenTerminalCommand(self.window)
        command.run(folders, parameters=parameters)


class OpenFolderInFilemanagerCommand(sublime_plugin.WindowCommand):
    def run(self):
        settings = sublime.load_settings('Terminal.sublime-settings')
        filemanager = get_platform_setting(settings, 'filemanager')
        if not filemanager:
            return
        if self.window.active_view():
            folder_name = os.path.dirname(self.window.active_view().file_name())
        elif self.window.folders():
            folder_name = self.window.folders()[0]
        # I could not test this on MacOS
        if sys.platform == "linux2" or sys.platform == "win32":
            subprocess.Popen([filemanager, folder_name])
