#!/usr/bin/env python
from __future__ import print_function
import sys
import os
import platform
import subprocess
try:
    # import tkinter as tk
    # from tkinter import ttk
    from tkinter import messagebox
except ImportError:
    # Python 2
    # import Tkinter as tk
    # import ttk
    import tkMessageBox as messagebox

verbose = False


def which(program, more_paths=[]):
    # Jay, & Mar77i. (2017, November 10). Path-Test if executable exists in
    #     Python? [Answer]. Stack Overflow.
    #     https://stackoverflow.com/questions/377017/
    #     test-if-executable-exists-in-python
    import os
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath = os.path.split(program)[0]
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in (os.environ["PATH"].split(os.pathsep) + more_paths):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


def error(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def debug(*args, **kwargs):
    if verbose:
        print(*args, file=sys.stderr, **kwargs)


blnkTemplate = '''Content-Type: text/blnk
Encoding=UTF-8
Type={Type}
Terminal={Terminal}
NoDisplay=true
Name={Name}
Comment=Open the file/directory (This was generated by blnk -s {Exec}).
Exec={Exec}
'''

'''
^ for blnk files not blnk itself
- for blnk itself, see dtLines.
- This should NOT have the MimeType key, which is used "to indicate the
  MIME Types that an application knows how to handle"
  -<https://specifications.freedesktop.org/desktop-entry-spec
  /desktop-entry-spec-latest.html>
'''

__doc__ = '''
Blnk (pronounced "blink") makes or runs a shortcut to a file or
directory.

The blnk format is (based on the XDG .desktop file format):
{Template}


If you run such a file and blnk runs it in a text editor, the problem
is that the first line must be the Content-Type line shown (It is case
sensitive), and there must not be any blank line before it.


Options:
-s                Create a shortcut to the given file.
--terminal        Specify "Terminal=true" in the blnk file to indicate
                    that the "Exec" file should run in a Terminal.

The following examples assume you've already made a symlink to blnk.py
as ~/.local/bin/blnk (and that ~/.local/bin is in your path--otherwise,
make the symlink as /usr/local/bin/blnk instead. On windows, make a
batch file that runs blnk and sends the parameters to it).

Create a shortcut:
blnk -s %SOME_PATH%

Where %SOME_PATH% is a full path to a blnk file without the
symbols. The new .blnk file will appear in the current working directory
and the name will be the same as the given filename but with the
extension changed to ".blnk".


Run a shortcut:
blnk %SOME_BLNK_FILE%

Where %SOME_BLNK_FILE% is a full path to a blnk file without the
symbols.

'''.format(Template=blnkTemplate)


# - Type is "Directory" or "File"
# - Name may be shown in the OS but usually isn't (from XDG .desktop
#   format).
# - Exec is the path to actually run (a directory or file). Environment
#   variables are allowed (with the symbols shown):
#   - %USERPROFILES%

class FileTypeError(Exception):
    pass

profile = None

myDirName = "blnk"
AppData = None
local = None
myLocal = None
shortcutsDir = None
replacements = None
username = None
profiles = None
logsDir = None
if platform.system() == "Windows":
    username = os.environ.get("USERNAME")
    profile = os.environ.get("USERPROFILE")
    _unused_ = os.path.join(profile, "AppData")
    AppData = os.path.join(_unused_, "Roaming")
    local = os.path.join(_unused_, "Local")
    share = local
    myShare = os.path.join(local, myDirName)
    shortcutsDir = os.path.join(profile, "Desktop")
    dtPath = os.path.join(shortcutsDir, "blnk.blnk")
    profiles = os.environ.get("PROFILESFOLDER")
    temporaryFiles = os.path.join(local, "Temp")
else:
    username = os.environ.get("USER")
    profile = os.environ.get("HOME")
    local = os.path.join(profile, ".local")
    share = os.path.join(local, "share")
    myShare = os.path.join(share, "blnk")
    if platform.system() == "Darwin":
        # See also <https://github.com/poikilos/world_clock>
        shortcutsDir = os.path.join(profile, "Desktop")
        Library = os.path.join(profile, "Library")
        AppData = os.path.join(Library, "Application Support")
        LocalAppData = os.path.join(Library, "Application Support")
        logsDir = os.path.join(profile, "Library", "Logs")
        profiles = "/Users"
        temporaryFiles = os.environ.get("TMPDIR")
    else:
        # GNU+Linux Systems
        shortcutsDir = os.path.join(share, "applications")
        AppData = os.path.join(profile, ".config")
        LocalAppData = os.path.join(profile, ".config")
        logsDir = os.path.join(profile, ".var", "log")
        profiles = "/home"
        temporaryFiles = "/tmp"
    dtPath = os.path.join(shortcutsDir, "blnk.desktop")
localBinPath = os.path.join(local, "bin")

statedCloud = "owncloud"
myCloud = "owncloud"
if os.path.isdir(os.path.join(profile, "Nextcloud")):
    myCloud = "Nextcloud"

# NOTE: PATH isn't necessary to split with os.pathsep (such as ":", not
# os.sep or os.path.sep such as "/") since sys.path is split already.

# The replacements are mixed since the blnk file may have come from
#   another OS:
substitutions = {
    "%USER%": username,
    "%USERPROFILE%": profile,
    "%PROFILESFOLDER%": profiles,
    "%MYDOCS%": os.path.join(profile, "Documents"),
    "%MYDOCUMENTS%": os.path.join(profile, "Documents"),
    "%APPDATA%": AppData,
    "%LOCALAPPDATA%": local,
    "%TEMP%": temporaryFiles,
    "%MYDOCS%": os.path.join(profile, "Documents"),
    "%APPDATA%": AppData,
    "$USER": username,
    "$HOME": profile,
    "~": profile,
}


def replace_isolated(path, old, new, case_sensitive=True):
    '''
    Replace old only if it is at the start or end of a path or is
    surrounded by os.path.sep.
    '''
    if case_sensitive:
        if path.startswith(old):
            path = new + path[len(old):]
        elif path.endswith(old):
            path = path[:-len(old)] + new
        else:
            wrappedNew = os.path.sep + new + os.path.sep
            wrappedOld = os.path.sep + old + os.path.sep
            path = path.replace(wrappedOld, wrappedNew)
    else:
        if path.lower().startswith(old.lower()):
            path = new + path[len(old):]
        elif path.lower().endswith(old.lower()):
            path = path[:-len(old)] + new
        else:
            wrappedNew = os.path.sep + new + os.path.sep
            wrappedOld = os.path.sep + old + os.path.sep
            at = 0
            while at >= 0:
                at = path.lower().find(old.lower())
                if at < 0:
                    break
                restI = at + len(old)
                path = path[:at] + new + path[restI:]
    return path


def replace_vars(path):
    for old,new in substitutions.items():
        if old.startswith("%") and old.endswith("%"):
            path = path.replace(old, new)
        else:
            path = replace_isolated(path, old, new)
    return path


def cmdjoin(parts):
    '''
    Join parts of a command. Add double quotes to each part that
    contains spaces.
    - There is no automatic sanitization (escape sequence generation).
    '''
    cmd = ""
    thisDelimiter = ""
    for i in range(len(parts)):
        part = parts[i]
        if " " in part:
            part = '"{}"'.format(part)
        cmd += thisDelimiter + part
        thisDelimiter = " "
    return cmd

def showErrorWindow(msg, title=("Blnk (Python {})"
                                "".format(platform.python_version()))):
    # from tkinter import messagebox
    error("{}: {}".format(title, msg))
    messagebox.showerror(title, msg)


myBinPath = __file__
tryBinPath = os.path.join(local, "bin", "blnk")
if os.path.isfile(tryBinPath):
    myBinPath = tryBinPath


class BLink:
    '''
    BASES is a list of paths that could contain the directory if the
    directory is a drive letter that is not C but the os is not Windows.
    '''
    NO_SECTION = "\n"
    BASES = [
        os.path.join(profile, myCloud),
        profile,
    ]
    USERS_DIRS = ["Users", "Documents and Settings"]

    def __init__(self, path, assignmentOperator="=",
                 commentDelimiter="#"):
        self.contentType = None
        self.contentTypeParts = None
        self.tree = {}
        self.lastSection = None
        self.path = None
        self.assignmentOperator = assignmentOperator
        self.commentDelimiter = commentDelimiter
        try:
            self.load(path)
        except FileTypeError as ex:
            raise ex

    def splitLine(self, line):
        i = line.find(self.assignmentOperator)
        if i < 0:
            tmpI = line.find(':')
            if tmpI >= 0:
                iPlus1C = line[tmpI+1:tmpI+2]
                iPlus2C = line[tmpI+2:tmpI+3]
                if (iPlus1C != "\\") or (iPlus2C == "\\"):
                    # ^ If iPlus2C == "\\", then the path may start with
                    # \\ (the start of a UNC network path).
                    self.assignmentOperator = ":"
                    error("* revering to deprecated ':' operator")
                    i = tmpI
                else:
                    error("WARNING: The line contains no '=', but ':'"
                          " seems like a path since it is followed by"
                          " \\ not \\\\")
        if i < 0:
            raise ValueError("The line contains no '{}': `{}`"
                             "".format(self.assignmentOperator,
                                       line))
        ls = line.strip()
        if self.isComment(ls):
            raise ValueError("splitLine doesn't work on comments.")
        if self.isSection(ls):
            raise ValueError("splitLine doesn't work on sections.")
        k = line[:i].strip()
        v = line[i+len(self.assignmentOperator):].strip()
        if self.commentDelimiter in v:
            error("WARNING: `{}` contains a comment delimiter '{}'"
                  " but inline comments are not supported."
                  "".format(line, self.commentDelimiter))
        return (k, v)

    def getSection(self, line):
        ls = line.strip()
        if ((len(ls) >= 2) and ls.startswith('[') and ls.endswith(']')):
            return ls[1:-1].strip()
        return None

    def isSection(self, line):
        return self.getSection(line) is not None

    def isComment(self, line):
        return line.strip().startswith(self.commentDelimiter)

    def _pushLine(self, line, row=None, col=None):
        '''
        Keyword arguments
        row -- Show this row (such as line_index+1) in syntax messages.
        col -- Show this col (such as char_index+1) in syntax messages.
        '''
        if row is None:
            if self.lastSection is not None:
                error("WARNING: The line `{}` was a custom line not on"
                      " a row of a file, but it will be placed in the"
                      " \"{}\" section which was still present."
                      "".format(line, self.lastSection))
        isContentTypeLine = False
        if self.contentType is None:
            ctOpener = "Content-Type:"
            if line.startswith(ctOpener):
                isContentTypeLine = True
                values = line[len(ctOpener):].split(";")
                for i in range(len(values)):
                    values[i] = values[i].strip()
                value = values[0]
                self.contentType = value
                self.contentTypeParts = values
        if self.contentType != "text/blnk":
            error("* running file directly due to:")
            raise FileTypeError(
                "The file must contain \"Content-Type:\""
                " (usually \"Content-Type: text/blnk\")"
                " before anything else, but"
                " _pushLine got \"{}\" (last file: {})"
                "".format(line, self.path)
            )
        if isContentTypeLine:
            return

        trySection = self.getSection(line)
        if self.isComment(line):
            pass
        elif trySection is not None:
            section = trySection
            if len(section) < 1:
                pre = ""  # This is a comment prefix for debugging.
                if lineN is not None:
                    if self.path is not None:
                        pre = self.path + ":"
                        if row is not None:
                            pre += str(row) + ":"
                            if col is not None:
                                pre += str(col) + ":"
                if len(pre) > 0:
                    pre += " "
                raise ValueError(pre+"_pushLine got an empty section")
            else:
                self.lastSection = section
        else:
            k, v = self.splitLine(line)
            '''
            if k == "Content-Type":
                self.contentType = v
                return
            '''
            section = self.lastSection
            if section is None:
                section = BLink.NO_SECTION
            sectionD = self.tree.get(section)
            if sectionD is None:
                sectionD = {}
                self.tree[section] = sectionD
            sectionD[k] = v

    def load(self, path):
        self.path = path
        try:
            with open(path, 'r') as ins:
                row = 0
                for line in ins:
                    row += 1
                    try:
                        self._pushLine(line, row=row)
                    except FileTypeError as ex:
                        error(str(ex))
                        error("* running file directly...")
                        self._choose_app(self.path)
                        raise ex
                self.lastSection = None
        except UnicodeDecodeError as ex:
            if path.lower().endswith(".blnk"):
                raise ex
            # else:
            # This is probably not a blnk file, so allow
            # the blank Exec handler to check the file extension.
            pass

    def getBranch(self, section, key):
        '''
        Get a tuple containing the section (section name key for
        self.tree) and the value self.tree[section][key]. The reason
        section is returned is in case the key doesn't exist there but
        exists in another section.
        '''
        v = None
        sectionD = self.tree.get(section)
        if sectionD is not None:
            v = sectionD.get(key)
        if v is None:
            section = None
            for trySection, sectionD in self.tree.keys():
                v = sectionD.get(key)
                if v is not None:
                    section = trySection
                    break
        return section, v

    def getExec(self):
        result = None
        trySection = BLink.NO_SECTION
        key = "Exec"
        section, v = self.getBranch(trySection, key)
        if v is None:
            path = self.path
            if path is not None:
                path = "\"" + path + "\""
            error("WARNING: There was no \"{}\" variable in {}"
                  "".format(key, path))
            return None
        elif section != trySection:
            sectionMsg = section
            if section == BLink.NO_SECTION:
                sectionMsg = "the main section"
            else:
                sectionMsg = "[{}]".format(section)
            error("WARNING: \"{}\" was in {}".format(key, sectionMsg))
        if v is None:
            return None
        path = v

        if platform.system() == "Windows":
            if v[1:2] == ":":
                if v[2:3] != "\\":
                    raise ValueError(
                        "The third character should be '\\' when the"
                        " 2nd character is ':', but the Exec value was"
                        " \"{}\"".format(v)
                    )

        else:  # Not windows
            if path.startswith("~/"):
                path = os.path.join(profile, path[2:])

            # Rewrite Windows paths **when on a non-Windows platform**:
            # error("  [blnk] v: \"{}\"".format(v))

            if v[1:2] == ":":

                # ^ Unless the leading slash is removed, join will
                #   ignore the param before it (will treat it as
                #   starting at the root directory)!
                # error("  v[1:2]: '{}'".format(v[1:2]))
                if v.lower() == "c:\\tmp":
                    path = temporaryFiles
                    debug("  [blnk] Detected {} as {}"
                          "".format(v, temporaryFiles))
                elif v.lower().startswith("c"):
                    debug("  [blnk] Detected c: in {}"
                          "".format(v.lower()))
                    path = v[3:].replace("\\", "/")
                    rest = path
                    # ^ Cut off C:\, so path may start with Users now:
                    statedUsersDir = None
                    for thisUsersDir in BLink.USERS_DIRS:
                        tryPath = thisUsersDir.lower() + "/"
                        if path.lower().startswith(tryPath):
                            statedUsersDir = thisUsersDir
                            break
                        else:
                            debug("  [blnk] {} doesn't start with {}"
                                  "".format(path.lower(),
                                            thisUsersDir.lower() + "/"))
                    debug("  [blnk] statedUsersDir: {}"
                          "".format(statedUsersDir))
                    if statedUsersDir is not None:
                        parts = path.split("/")
                        # error("  [blnk] parts={}".format(parts))
                        if len(parts) > 1:
                            rel = ""
                            if len(parts[2:]) > 0:
                                rel = parts[2:][0]
                                old = parts[:2][0]
                                if len(parts[2:]) > 1:
                                    rel = os.path.join(*parts[2:])
                                if len(parts[:2]) > 1:
                                    old = os.path.join(*parts[:2])
                                # ^ splat ('*') since join takes
                                #   multiple params not a list.
                                debug("  [blnk] changing \"{}\" to"
                                      " \"{}\"".format(old, profile))
                                path = os.path.join(profile, rel)
                            else:
                                path = profile
                        else:
                            path = profile
                    elif path.lower() == "users":
                        path = profiles
                    else:
                        path = os.path.join(profile, rest)
                        error("  [blnk] {} was forced due to bad path:"
                              " \"{}\".".format(path, v))
                else:
                    debug("Detected drive letter that is not C:")
                    # It starts with letter+colon but letter is NOT c.
                    path = v.replace("\\", "/")
                    rest = path[3:]
                    isGood = False
                    for thisBase in BLink.BASES:
                        debug("  [blnk] thisBase: \"{}\""
                              "".format(thisBase))
                        debug("  [blnk] rest: \"{}\""
                              "".format(rest))
                        tryPath = os.path.join(thisBase, rest)
                        debug("  [blnk] tryPath: \"{}\""
                              "".format(tryPath))
                        if os.path.exists(tryPath):
                            path = tryPath
                            # Change something like D:\Meshes to
                            # /home/x/Nextcloud/Meshes or use some other
                            # replacement for D:\ that is in BASES.
                            error("  [blnk] {} was detected."
                                  "".format(tryPath))
                            isGood = True
                            break
                        else:
                            error("  [blnk] {} doesn't exist."
                                  "".format(tryPath))
                    if not isGood:
                        # Force it to be a non-Window path even if it
                        # doesn't exist, but use the home directory
                        # so it is a path that makes some sort of sense
                        # to everyone even if they don't have the
                        path = os.path.join(profile, rest)
                        error("  [blnk] {} was forced due to bad path:"
                              " \"{}\".".format(path, v))
            else:
                path = v.replace("\\", "/")

        path = replace_vars(path)
        path = replace_isolated(path, statedCloud, myCloud,
                                case_sensitive=False)
        if path != v:
            error("  [blnk] changing \"{}\" to"
                  " \"{}\"".format(v, path))
        return path

    @staticmethod
    def _run_parts(parts, check=True):
        error("* running \"{}\"...".format(parts))
        runner = subprocess.check_call
        use_check = False
        if hasattr(subprocess, 'run'):
            # Python 3
            use_check = True
            runner = subprocess.run
            error("  - using subprocess.run")
            part0 = which(parts[0])
            # if localPath not in os.environ["PATH"].split(os.pathsep):
            if part0 is None:
                part0 = which(parts[0], more_paths=[localBinPath])
                if part0 is not None:
                    parts[0] = part0
        else:
            error("  - using Python 2 subprocess.check_call"
                  " from Python {}"
                  "".format(platform.python_version()))
            # check_call requires a full path (!):
            if not os.path.isfile(parts[0]):
                part0 = which(parts[0], more_paths=[localBinPath])
                if part0 is not None:
                    parts[0] = part0
        try:
            if use_check:
                runner(parts, check=check)
            else:
                runner(parts)
        except FileNotFoundError as ex:
            pathMsg = (" (The system path wasn't checked"
                       " since the executable part is a path)")
            if os.path.split(parts[0])[1] == parts[0]:
                # It is a filename not a path.
                pathMsg = (" ({} is not in the system path)"
                           "".format(parts[0]))
            showErrorWindow(
                "Running external application `{}` for a non-blnk file"
                " failed{}:"
                " {}".format(cmdjoin(parts), pathMsg, ex),
            )
            raise ex
        except Exception as ex:
            showErrorWindow(
                "Running external application `{}` for a non-blnk file"
                " failed: {}".format(cmdjoin(parts), ex),
            )
            raise ex
        '''
        except TypeError as ex:
            # should only happen if sending check=check when runner
            # is check_call--which doesn't work since check is only a
            # keyword argument when runner is run.
            if "unexpected keyword argument 'check'" in str(ex):
                try:
                    runner(parts)
                except FileNotFoundError as ex:
                    showErrorWindow(
                        "{}".format(ex),
                    )
                    raise ex
            else:
                raise ex
        '''
    @staticmethod
    def _run(path):
        tryCmd = "xdg-open"
        # TODO: try os.popen('open "{}"') on mac
        # NOTE: %USERPROFILE%, $HOME, ~, or such should already be
        #   replaced by getExec.
        if platform.system() == "Windows":
            if (len(path) >= 2) and (path[1] == ":"):
                if not os.path.exists(path):
                    showErrorWindow("The path doesn't exist: {}"
                                    "".format(path))
                    return
            os.startfile(path, 'open')
            # runner('cmd /c start "{}"'.format(path))
            return
        thisOpenCmd = None
        try:
            thisOpenCmd = tryCmd
            error("  - {}...".format(thisOpenCmd))
            BLink._run_parts([thisOpenCmd, path], check=True)
        except OSError as ex:
            try:
                thisOpenCmd = "open"
                error("  - {}...".format(thisOpenCmd))
                BLink._run_parts([thisOpenCmd, path], check=True)
            except OSError as ex:
                thisOpenCmd = "xdg-launch"
                error("  - trying {}...".format(thisOpenCmd))
                BLink._run_parts([thisOpenCmd, path], check=True)
        except subprocess.CalledProcessError as ex:
            showErrorWindow("{} couldn't open the path: \"{}\""
                            "".format(thisOpenCmd, path))

    def _choose_app(self, path):
        error("  - choosing app for \"{}\"".format(path))
        app = "geany"
        # If you set blnk to handle unknown files:
        more_parts = []
        if path.lower().endswith(".kdb"):
            app = "keepassxc"
        elif path.lower().endswith(".kdbx"):
            app = "keepassxc"
        elif path.lower().endswith(".nja"):
            app = "ninja-ide"
            more_parts = ["-p"]  # required for running project files
            path = os.path.split(path)[0]
            # ^ With the -p option, Ninja-IDE will only open a directory
            #   (with or without an nja file) not the nja file itself.
        error("    - {}".format(app))
        BLink._run_parts([app] + more_parts + [path])

    def run(self):
        execStr = self.getExec()
        if execStr is None:
            error("* Exec is None...")
            self._choose_app(self.path)
            return
        BLink._run(execStr)

dtLines = [
    "[Desktop Entry]",
    "Exec={}".format(myBinPath),
    "MimeType=text/blnk;",
    "NoDisplay=true",
    "Name=blnk".format(myBinPath),
    "Type=Application",
]
#
#   Don't set NoDisplay:true or it can't be seen in the "Open With" menu
#   such as in Caja (MATE file explorer)
#   - This is for blnk itself. For blnk files, see blnkTemplate.



def usage():
    print(__doc__)


def main(args):
    error("* checking for \"{}\"".format(dtPath))
    if not os.path.isfile(dtPath):
        error("* writing \"{}\"...".format(dtPath))
        if not os.path.isdir(shortcutsDir):
            os.makedirs(shortcutsDir)
        with open(dtPath, 'w') as outs:
            for line in dtLines:
                outs.write(line + "\n")
        if not platform.system == "Windows":
            error("  - installing...")
            iconCommandParts = ["xdg-desktop-icon", "install",
                                "--novendor"]
            cmdParts = iconCommandParts + [dtPath]
            try:
                BLink._run_parts(cmdParts)
            except subprocess.CalledProcessError:
                # os.remove(dtPath)
                # ^ Force automatically recreating the icon.
                error("{} failed.".format(cmdParts))
                error(str(cmdParts))

    if len(args) < 2:
        usage()
        raise ValueError("Error: The first argument is the program but"
                         " there is no argument after that. Provide a"
                         " file path.")
    MODE_RUN = "run"
    MODE_CS = "create shortcut"
    mode = MODE_RUN
    path = None
    Terminal = "false"
    for i in range(1, len(args)):
        arg = args[i]
        if arg == "-s":
            mode = MODE_CS
        elif arg == "--terminal":
            Terminal = "true"
        else:
            if path is None:
                path = arg
            else:
                raise ValueError("The option \"{}\" is unknown and the"
                                 " path was already \"{}\""
                                 "".format(arg, path))
    if path is None:
        usage()
        error("Error: The path was not set (args={}).".format(args))
        exit(1)
    Type = None
    if os.path.isdir(path):
        Type = "Directory"
    elif os.path.isfile(path):
        Type = "File"
    if Type is None:
        usage()
        error("Error: The path \"{}\" is not a file or directory"
              " (args={}).".format(path, args))
        exit(1)

    if mode == MODE_RUN:
        try:
            link = BLink(path)
            link.run()
        except FileTypeError:
            pass
            # already handled by Blink
    elif mode == MODE_CS:
        Name = os.path.splitext(os.path.split(path)[-1])[0]
        newName = Name + ".blnk"
        newPath = newName
        # ^ Use the current directory, so do not use the full path.
        content = blnkTemplate.format(Type=Type, Name=Name, Exec=path,
                                      Terminal=Terminal)
        # error(content)
        if os.path.exists(newPath):
            error("Error: {} already exists.".format(newPath))
            exit(1)
        with open(newPath, 'w') as outs:
            outs.write(content)
        error("* wrote \"{}\"".format(newPath))
    else:
        raise NotImplementedError("The mode \"{}\" is not known."
                                  "".format(mode))


if __name__ == "__main__":
    main(sys.argv)
