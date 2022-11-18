#!/usr/bin/env python3

# See __doc__ further down for documentation.

from __future__ import print_function
import sys
import os
import platform
import subprocess
import traceback
import pathlib
import shlex
from datetime import (
    datetime,
    timezone,
)

ENABLE_TK = False
if sys.version_info.major >= 3:
    try:
        import tkinter as tk
        # from tkinter import ttk
        from tkinter import messagebox
        ENABLE_TK = True
    except ModuleNotFoundError:
        pass
else:
    try:
        import Tkinter as tk
        # import ttk
        import tkMessageBox as messagebox
        ENABLE_TK = True
    except ModuleNotFoundError:
        pass

# Handle issues where the OS considers "BLNK" and all of these file
#   extensions as "text/plain" rather than allowing them to be
#   associated with separate programs.
associations = {
    ".kdb": ["keepassxc"],
    ".kdbx": ["keepassxc"],
    ".pyw": ["python"],
    ".py": ["python"],
    ".nja": ["ninja-ide", "-p"],  # required for opening project files
    ".csv": ["libreoffice", "--calc"],
    ".csv": ["/usr/bin/flatpak", "run", "--branch=stable", "--arch=x86_64",
             "--command=libreoffice", "org.libreoffice.LibreOffice", "--calc"],
    ".pdf": ["xdg-open"],  # changed below (See preferred_pdf_viewers loop)
}
# ^ Each value can be a string or list.
# ^ Besides associations there is also a special case necessary for
#   ninja-ide to change the file to the containing folder (See
#   associations code further down).
settings = {
    "file_type_associations": associations,
}

# preferred_pdf_viewers = ["qpdfview", "atril", "evince"]
# ^ evince is the GNOME and MATE "Document Viewer".
preferred_pdf_viewers = []

verbosity = 0

for argI in range(1, len(sys.argv)):
    arg = sys.argv[argI]
    if arg.startswith("--"):
        if arg == "--debug":
            verbosity = 2
        elif arg == "--verbose":
            verbosity = 1

verbosities = [True, False, 0, 1, 2]


def set_verbosity(level):
    global verbosity
    if level not in verbosities:
        raise ValueError("level must be one of {}".format(verbosities))
    verbosity = level
    echo0("verbosity={}".format(verbosity))


def which(program, more_paths=[]):
    # Jay, & Mar77i. (2017, November 10). Path-Test if executable exists in
    #     Python? [Answer]. Stack Overflow.
    #     https://stackoverflow.com/questions/377017/
    #     test-if-executable-exists-in-python
    import os

    def is_exe(fpath):
        # The fpath param name DIFFERS since it is an inline function.
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


path = None
for try_pdf_viewer in preferred_pdf_viewers:
    path = which(try_pdf_viewer)
    if path is not None:
        associations[".pdf"][0] = try_pdf_viewer
        break
del path


def echo0(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def echo1(*args, **kwargs):
    if verbosity < 1:
        return False
    print(*args, file=sys.stderr, **kwargs)
    return True


def echo2(*args, **kwargs):
    if verbosity < 2:
        return False
    print(*args, file=sys.stderr, **kwargs)
    return True


# region same as pycodetool
# syntax_error_fmt = "{path}:{row}:{column}: {message}"
syntax_error_fmt = 'File "{path}", line {row}, {column} {message}'
# ^ such as (Python-style, so readable by Geany):
'''
  File "/redacted/git/pycodetool/pycodetool/spec.py", line 336, in read_spec
'''


def set_syntax_error_fmt(fmt):
    global syntax_error_fmt
    syntax_error_fmt = fmt


def to_syntax_error(path, lineN, msg, col=None):
    '''
    Convert the error to a syntax error that specifies the file and line
    number that has the bad syntax.

    Keyword arguments:
    col -- is the character index relative to the start of the line,
        starting at 1 for compatibility with outputinspector (which will
        subtract 1 if using editors that start at 0).
    '''
    this_fmt = syntax_error_fmt

    if col is None:
        part = "{column}"
        removeI = this_fmt.find(part)
        if removeI > -1:
            suffixI = removeI + len(part) + 1
            # ^ +1 to get punctuation!
            this_fmt = this_fmt[:removeI] + this_fmt[suffixI:]
    if lineN is None:
        part = "{row}"
        removeI = this_fmt.find(part)
        if removeI > -1:
            suffixI = removeI + len(part) + 1
            # ^ +1 to get punctuation!
            this_fmt = this_fmt[:removeI] + this_fmt[suffixI:]
    return this_fmt.format(path=path, row=lineN, column=col, message=msg)
    # ^ Settings values not in this_fmt is ok.


def echo_SyntaxWarning(path, lineN, msg, col=None):
    msg = to_syntax_error(path, lineN, msg, col=col)
    echo0(msg)
    # ^ So the IDE can try to parse what path&line has an error.


def raise_SyntaxError(path, lineN, msg, col=None):
    echo_SyntaxWarning(path, lineN, msg, col=col)
    raise SyntaxError(msg)

# endregion same as pycodetool


def get_traceback(indent=""):
    ex_type, ex, tb = sys.exc_info()
    msg = "{}{} {}:\n".format(indent, ex_type, ex)
    msg += traceback.format_exc()
    del tb
    return msg


def view_traceback(indent=""):
    ex_type, ex, tb = sys.exc_info()
    print("{}{} {}: ".format(indent, ex_type, ex), file=sys.stderr)
    traceback.print_tb(tb)
    del tb
    print("", file=sys.stderr)


'''
### XDG specification issue
There is apparently an issue in the XDG desktop spec where
Type=Desktop has no specified key for the path. Poikilos e-mailed
the XDG mailing list about it to report the issue (2022-11-02 from gmail
and it came back through the system indicating it was sent to list
members). I mentioned that blnk implements the suggested additions to
the specification.

See also: "[Why not use Desktop
Entry](doc/development.md#Why not use Desktop Entry)" in
doc/development.md
'''


blnkTemplate = '''[X-Blnk]
Type={Type}
Terminal={Terminal}
NoDisplay=true
Name={Name}
Comment=Shortcut generated by 'blnk -s "{Exec}"'.
Exec={Exec}

[X-Target Metadata]
modified={mtime}
created={ctime}
'''

fileOrDirTemplate = '''[X-Blnk]
Type={Type}
NoDisplay=true
Name={Name}
Comment=Shortcut generated by 'blnk -s "{Path}"'.
Path={Path}

[X-Target Metadata]
modified={mtime}
created={ctime}
'''

blnkURLTemplate = '''[X-Blnk]
Type={Type}
Terminal={Terminal}
NoDisplay=true
Name={Name}
Comment=Open the URL (This was generated by 'blnk -s "{URL}" "{Name}"').
URL={URL}
Icon=folder-remote

[X-Target Metadata]
accessed={accessed}
'''

'''
In XDG Format:
- "X-" must start each section name that extends the format.
- "Encoding=UTF-8" is deprecated.


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
                    that the 'Exec' file should run in a Terminal.

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


from find_hierosoft import hierosoft

from hierosoft import (  # formerly blnk.morefolders
    replace_isolated,
    replace_vars,
    localBinPath,
    HOME,
    SHORTCUTS_DIR,
    PROFILES,
    temporaryFiles,
)


def not_quoted(s, key=""):
    '''
    Keyword arguments:
    key -- set the name of the variable (only for verbose messages).
    '''
    if s is None:
        return None
    for q in ['"', "'"]:
        if (len(s) > 1) and s.startswith(q) and s.endswith(q):
            return s[1:-1]
            echo1("trimmed quotes from: {}={}".format(key, s))
            break
        else:
            echo1("using already not quoted: {}={}".format(key, s))
    return s


def is_url(path):
    path = path.lower()
    endProtoI = path.find("://")
    if endProtoI > 0:
        # TODO: Check for known protocols? Check for "file" protocol?
        return True
    return False


def showMsgBoxOrErr(msg,
                    title="Blnk (Python {})".format(sys.version_info.major),
                    try_gui=True):
    # from tkinter import messagebox
    echo0("{}\nusing {}".format(msg, title))
    print("try_gui={}".format(try_gui))
    if not try_gui:
        return
    try:
        messagebox.showerror(title, msg)
    except tk.TclError as ex:
        if "no display" in str(ex):
            # "no display and no $DISPLAY environment variable"
            # (The user is not in a GUI session)
            pass
        else:
            raise ex


myBinPath = __file__
tryBinPath = os.path.join(localBinPath, "blnk")
if os.path.isfile(tryBinPath):
    myBinPath = tryBinPath


class BLink:
    '''
    BASES is a list of paths that could contain the directory if the
    directory is a drive letter that is not C but the os is not Windows.
    '''
    NO_SECTION = "\n"
    BASES = [
        HOME,
    ]
    cloud_path = replace_vars("%CLOUD%")
    # ^ Does return None if the entire string is one var that is blank.
    cloud_name = None
    echo0('cloud_path="{}"'.format(cloud_path))
    if cloud_path is not None:
        # myCloud = myCloudName
        # if myCloud is None:
        #     myCloud = "Nextcloud"
        # os.path.join(HOME, myCloud)
        BASES.append(cloud_path)
        cloud_name = os.path.split(cloud_path)[1]
    echo0('cloud_name="{}"'.format(cloud_name))

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

    def getAbs(self, path):
        rawPath = path
        if not os.path.exists(path):
            # See if it is relative to the blnk file.
            tryPath = os.path.join(os.path.dirname(self.path), path)
            if os.path.exists(tryPath):
                # path = os.path.realpath(tryPath)
                path = os.path.abspath(tryPath)
                print('* redirecting "{}" to "{}"'.format(rawPath, path))
        else:
            path = os.path.abspath(path)
        return path

    def splitLine(self, line, path=None, row=None):
        '''
        Keyword arguments:
        path -- The source of the data (only for tracing errors).
        row -- The source of the data in the file named path (only for
            tracing errors).
        '''
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
                    echo0("* reverting to deprecated ':' operator")
                    i = tmpI
                else:
                    echo_SyntaxWarning(
                        path,
                        row,
                        "WARNING: The line contains no '=', but ':'"
                        " seems like a path since it is followed by"
                        " \\ not \\\\",
                    )
        if i < 0:
            raise_SyntaxError(path, row,
                              "The line contains no '{}': `{}`"
                              "".format(self.assignmentOperator, line))
        ls = line.strip()
        if self.isComment(ls):
            raise ValueError("splitLine doesn't work on comments.")
        if self.isSection(ls):
            raise ValueError("splitLine doesn't work on sections.")
        k = line[:i].strip()
        v = line[i+len(self.assignmentOperator):].strip()
        if self.commentDelimiter in v:
            # if k != "URL":
            echo_SyntaxWarning(
                path,
                row,
                "WARNING: `{}` contains a comment delimiter '{}'"
                " but inline comments are not supported."
                "".format(line, self.commentDelimiter),
            )
            # URL may have a # that is not a comment.
            # If the URL blnk file was automatically generated such as
            #   with the blnk -s command, then the Name and Comment will
            #   contain the character as well since they are generated
            #   from the target.
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

    def _pushLine(self, rawL, row=None, col=None, path=None):
        '''
        Keyword arguments
        path -- Show this path in syntax messages.
        row -- Show this row (such as line_index+1) in syntax messages.
        col -- Show this col (such as char_index+1) in syntax messages.
        '''
        line = rawL.strip()
        if len(line) < 1:
            return
        if row is None:
            if self.lastSection is not None:
                echo0("WARNING: The line `{}` was a custom line not on"
                      " a row of a file, but it will be placed in the"
                      " \"{}\" section which was still present."
                      "".format(line, self.lastSection))
        isContentTypeLine = False
        if line == "[X-Blnk]":
            isContentTypeLine = True
            value = "text/blnk"
            self.contentType = value
            self.contentTypeParts = [value]
        elif self.contentType is None:
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
            print("* running non-blnk file directly")
            raise FileTypeError(
                "The file must contain \"Content-Type:\""
                " (usually \"Content-Type: text/blnk\")"
                " before anything else, but"
                " _pushLine got \"{}\" (last file: {})"
                "".format(line, self.path)
            )
        if isContentTypeLine:
            return
            # ^ For backward compatibility, don't actually make X-Blnk a
            #   section (Return before that).

        trySection = self.getSection(line)
        # ^ OK since return occurred above if isContentTypeLine
        if self.isComment(line):
            pass
        elif trySection is not None:
            section = trySection
            if len(section) < 1:
                pre = ""  # This is a comment prefix for debugging.
                if row is not None:
                    if self.path is not None:
                        pre = self.path + ":"
                        if row is not None:
                            pre += str(row) + ":"
                            if col is not None:
                                pre += str(col) + ":"
                if len(pre) > 0:
                    pre += " "
                raise raise_SyntaxError(
                    path,
                    row,
                    pre+"_pushLine got an empty section",
                )
            else:
                self.lastSection = section
        else:
            k, v = self.splitLine(line, path=path, row=row)
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
                        self._pushLine(line, path=path, row=row)
                    except FileTypeError as ex:
                        # Do not produce error messages for the bash
                        # script to show in the GUI since this is
                        # recoverable (and expected if plain text files
                        # are associated with blnk.
                        print(str(ex))
                        print("* running file directly...")
                        return self._choose_app(self.path)
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
            for trySection, sectionD in self.tree.items():
                v = sectionD.get(key)
                if v is not None:
                    section = trySection
                    break
        return section, v

    def get(self, key):
        section = BLink.NO_SECTION
        got_section, v = self.getBranch(section, key)
        if got_section is None:
            # It is using the latest format.
            got_section, v = self.getBranch("[X-Blnk]", key)
        old_v = v
        v = not_quoted(v, key=key)
        return v

    def getExec(self, key='Exec'):
        '''
        Be careful when filling in paths from cwd here. This function
        will keep the quotes to ensure paths with spaces work, and to
        ensure the original syntax of the line is kept. To avoid issues:
        - *always* use shlex.split on the output from this method.
        '''
        trySection = BLink.NO_SECTION
        section, v = self.getBranch(trySection, key)
        # Warning: don't remove quotes yet, because shlex.split
        #   is done later! Removing the quotes now would split more
        #   parts than should be.

        if v is None:
            path = self.path
            if path is not None:
                path = "\"" + path + "\""
            msg = ("WARNING: There was no \"{}\" variable in {}"
                   "".format(key, path))
            return None, msg
        elif section != trySection:
            sectionMsg = section
            if section == BLink.NO_SECTION:
                sectionMsg = "the main section"
            else:
                sectionMsg = "[{}]".format(section)
            msg = "WARNING: \"{}\" was in {}".format(key, sectionMsg)
        if v is None:
            return None, msg
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
                path = os.path.join(HOME, path[2:])

            # Rewrite Windows paths **when on a non-Windows platform**:
            # print("  [blnk] v: \"{}\"".format(v))

            if v[1:2] == ":":

                # ^ Unless the leading slash is removed, join will
                #   ignore the param before it (will treat it as
                #   starting at the root directory)!
                # print("  v[1:2]: '{}'".format(v[1:2]))
                if v.lower() == "c:\\tmp":
                    path = temporaryFiles
                    echo1("  [blnk] Detected {} as {}"
                          "".format(v, temporaryFiles))
                elif v.lower().startswith("c"):
                    echo1("  [blnk] Detected c: in {}"
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
                            echo1("  [blnk] {} doesn't start with {}"
                                  "".format(path.lower(),
                                            thisUsersDir.lower() + "/"))
                    echo1("  [blnk] statedUsersDir: {}"
                          "".format(statedUsersDir))
                    if statedUsersDir is not None:
                        parts = path.split("/")
                        # print("  [blnk] parts={}".format(parts))
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
                                echo1("  [blnk] changing \"{}\" to"
                                      " \"{}\"".format(old, HOME))
                                path = os.path.join(HOME, rel)
                            else:
                                path = HOME
                        else:
                            path = HOME
                    elif path.lower() == "users":
                        path = PROFILES
                    else:
                        path = os.path.join(HOME, rest)
                        echo0("  [blnk] {} was forced due to bad path:"
                              " \"{}\".".format(path, v))
                else:
                    echo1("Detected drive letter that is not C:")
                    # It starts with letter+colon but letter is NOT c.
                    path = v.replace("\\", "/")
                    rest = path[3:]
                    isGood = False
                    for thisBase in BLink.BASES:
                        echo1("  [blnk] thisBase: \"{}\""
                              "".format(thisBase))
                        echo1("  [blnk] rest: \"{}\""
                              "".format(rest))
                        tryPath = os.path.join(thisBase, rest)
                        echo1("  [blnk] tryPath: \"{}\""
                              "".format(tryPath))
                        if os.path.exists(tryPath):
                            path = tryPath
                            # Change something like D:\Meshes to
                            # /home/x/Nextcloud/Meshes or use some other
                            # replacement for D:\ that is in BASES.
                            print("  [blnk] {} was detected."
                                  "".format(tryPath))
                            isGood = True
                            break
                        else:
                            echo0("  [blnk] {} doesn't exist."
                                  "".format(tryPath))
                    if not isGood:
                        # Force it to be a non-Window path even if it
                        # doesn't exist, but use the home directory
                        # so it is a path that makes some sort of sense
                        # to everyone even if they don't have the
                        path = os.path.join(HOME, rest)
                        echo0("  [blnk] {} was forced due to bad path:"
                              " \"{}\".".format(path, v))
            else:
                path = v.replace("\\", "/")

        path = replace_vars(path)
        if BLink.cloud_name is not None:
            for statedCloud in ["ownCloud", "owncloud"]:
                path = replace_isolated(path, statedCloud,
                                        BLink.cloud_name,
                                        case_sensitive=False)

        old_parts = shlex.split(path)
        # if not os.path.exists(old_parts[0]):
        abs0 = self.getAbs(old_parts[0])
        if old_parts[0] == abs0:
            if not os.path.exists(old_parts[0]):
                print('  [blnk] "{}"'
                      ' wasn\'t an existing absolute or relative path"'
                      ''.format(old_parts[0]))
        old_parts[0] = abs0
        path = shlex.join(old_parts)
        # else:
        #    print('* using existing relative target "{}"'.format(old_parts))

        if path != v:
            print("  [blnk] changing \"{}\" to"
                  " \"{}\"".format(v, path))
        return path, None

    @staticmethod
    def _run_parts(parts, check=True, cwd=None, target_blnk_type=False):
        '''
        Run a command (list of command and args) directly using the best
        call depending on the Python version.

        Keyword arguments:
        cwd -- Change to this working directory first. This
            should not usually be set to anything except the Path field
            of a .blnk (or .desktop) file.
            - Warning: A value other than None will cause subprocess to
              FileNotFoundError for some reason if running
              `['xdg-open', DirectoryPath]`.

        is_blnk_type -- You can set this to True if the file type is
            associated with blnk to prevent infinite recursion between
            xdg-open and blnk.
        check -- Set the "check" option of subprocess if available in
            the version of Python that is running this module.
        '''
        if cwd is not None:
            if not_quoted(cwd) != cwd:
                raise ValueError("cwd must not be quoted!")
        for i in range(len(parts)):
            if not_quoted(parts[i]) != parts[i]:
                raise ValueError(
                    "parts[{}] must not be quoted but is {}!"
                    "".format(i, parts[i])
                )
        if (len(parts) > 1) and (parts[1] == cwd):
            echo0('Warning: not using cwd="{}" since that is the target.'
                  ''.format(cwd))
            cwd = None
        # if cwd is not None:
        #     os.chdir(cwd)
        # ^ Use the cwd param of run or check_call instead.
        print('* running "{}" (in "{}")...'.format(parts, os.getcwd()))
        if target_blnk_type and (parts[0] == "xdg-open"):
            raise ValueError(
                'xdg-open was blocked to prevent infinite recursion'
                ' in case the file type of {} is associated with blnk.'
                ''.format(parts[1:])
            )
        # else: There should be no infinite recursion if the document is
        #   not a type associated with blnk such as plain text.

        run_fn = subprocess.check_call
        run_fn_name = "subprocess.check_call"
        use_check = False
        if len(parts) > 1:
            if not os.path.exists(parts[1]):
                echo1('Warning: "{}" does not exist.'.format(parts[1]))
            else:
                echo1('INFO: "{}" was found.'.format(parts[1]))
        if hasattr(subprocess, 'run'):
            # Python 3
            use_check = True
            run_fn = subprocess.run
            run_fn_name = "subprocess.run"
            print("  - run_fn=subprocess.run")
            part0 = which(parts[0])
            # if localPath not in os.environ["PATH"].split(os.pathsep):
            if part0 is None:
                part0 = which(parts[0], more_paths=[localBinPath])
                if part0 is not None:
                    parts[0] = part0
        else:
            print("  - using Python 2 subprocess.check_call"
                  " from Python {}"
                  "".format(sys.version_info.major))
            # check_call requires a full path (!):
            if not os.path.isfile(parts[0]):
                part0 = which(parts[0], more_paths=[localBinPath])
                if part0 is not None:
                    parts[0] = part0
        completedprocess = None
        returncode = None
        try:
            echo1("run_fn={}".format(run_fn_name))
            if use_check:
                echo1("* using check")
                if cwd is not None:
                    echo1("* manually-set cwd is None")
                    # parts[0] = which(parts[0])
                    echo1('parts[0]="{}"'.format(parts[0]))
                    # Warning: If cwd is not None subprocess will raise
                    #   FileNotFoundError if running
                    #   ['xdg-open', DirectoryPath]!
                    completedprocess = run_fn(parts, check=check, cwd=cwd)
                else:
                    echo1("* manually-set cwd is {}".format(cwd))
                    completedprocess = run_fn(parts, check=check)
            else:
                echo1("* not using check")
                if cwd is not None:
                    echo1("* manually-set cwd is None")
                    completedprocess = run_fn(parts, cwd=cwd)
                else:
                    echo1("* manually-set cwd is {}".format(cwd))
                    completedprocess = run_fn(parts)
            if completedprocess is not None:
                if hasattr(completedprocess, "returncode"):
                    returncode = completedprocess.returncode
            echo0("returncode={}".format(completedprocess.returncode))
        except FileNotFoundError as ex:
            echo0("parts={}".format(parts))
            pathMsg = (" (The system path wasn't checked"
                       " since the executable part is a path)")
            if os.path.split(parts[0])[1] == parts[0]:
                # It is a filename not a path.
                pathMsg = (" ({} may not be in the system path,"
                           " or maybe blnk set cwd and shouldn't have)"
                           "".format(parts[0]))
            raise FileNotFoundError(
                "Running external application `{}` for a non-blnk file"
                " failed{}:"
                " {}".format(shlex.join(parts), pathMsg, ex),
            )
        except FileNotFoundError as ex:
            echo0(get_traceback())
            raise FileNotFoundError(
                'The file was not found: '
                ' {} ({})'.format(shlex.join(parts), ex),
            )
        except Exception as ex:
            raise ex
        '''
        except TypeError as ex:
            # should only happen if sending check=check when run_fn
            # is check_call--which doesn't work since check is only a
            # keyword argument when run_fn is run.
            if "unexpected keyword argument 'check'" in str(ex):
                try:
                    run_fn(parts)
                except FileNotFoundError as ex:
                    raise ex
            else:
                raise ex
        '''
        return 0

    @staticmethod
    def _run(Exec, Type, cwd=None):
        '''
        This is a static method, so any object attributes must be
        provided as arguments.

        Run the correct path automatically using the Type variable from
        the blnk file (Type can be Directory, File, OR Application).
        Note that the "Path" key sets the working directory NOT the
        target, but the Exec argument is equivalent to 'Exec'.

        Sequential arguments:
        Exec -- Should be the Exec value if Type is Application, Path if
            a File or Directory, or URL if a Link.

        Keyword arguments:
        cwd -- Set this to the value of the 'Path' key if present to set
            the current working directory in the subprocess.
        '''
        echo1('* _run("{}", "{}", cwd="")'.format(Exec, Type, cwd))
        tryCmd = "geany"
        # TODO: try os.popen('open "{}"') on mac
        # NOTE: %USERPROFILE%, $HOME, ~, or such should already be
        #   replaced by getExec.
        exists_fn = os.path.isfile
        execParts = shlex.split(Exec)
        if len(execParts) > 1:
            Exec = execParts[0]
        if Type == "Directory":
            exists_fn = os.path.isdir
        elif Type == "Application":
            echo0('* running application {}'.format(execParts))
            return BLink._run_parts(execParts, check=True, cwd=cwd)
        elif Type == "Link":
            def true_fn():
                echo0('* assuming "{}" exists.'.format(Exec))
                return True
            exists_fn = true_fn

        if platform.system() == "Windows":
            if (len(Exec) >= 2) and (Exec[1] == ":"):
                # starts with "C:" or another drive letter
                if not os.path.exists(Exec):
                    raise FileNotFoundError(
                        "The Exec target doesn't exist: {}"
                        "".format(Exec)
                    )
            os.startfile(Exec, 'open')
            # run_fn('cmd /c start "{}"'.format(Exec))
            return 0
        if Type == "Directory":
            echo0('* opening directory "{}"'.format(Exec))
            execParts = ['xdg-open', not_quoted(Exec, key='_run() arg')]
            return BLink._run_parts(execParts, check=True, cwd=cwd)
        thisOpenCmd = None
        if "://" not in Exec:
            if not exists_fn(Exec):
                raise FileNotFoundError(
                    '"{}"'
                    ''.format(Exec)
                )
        if Type == "Link":
            thisOpenCmd = 'xdg-open'
            '''
            if len(parts) == 1:
                raise ValueError(
                    "_run expected ['xdg-open', '{}'] (or some program"
                    " for opening a URL) but only got {}"
                    "".format(parts[1], parts)
                )
            '''
            return BLink._run_parts([thisOpenCmd, Exec], check=True)
        try:
            if Type == "File":
                # thisOpenCmd = tryCmd
                # FIXME: There should be a better way to solve this. The
                #   infinite recursion only happens if the type of file
                #   being opened (The file type of the path in the Exec
                #   line) is associated with blnk.
                echo0("  - thisOpenCmd={}...".format(thisOpenCmd))
                if thisOpenCmd == "xdg-open":
                    raise ValueError(
                        'xdg-open was blocked to prevent infinite'
                        ' recursion in case the file type of {} is'
                        ' associated with blnk.'
                        ''.format()
                    )
                return BLink._run_parts([thisOpenCmd, Exec], check=True)
        except OSError as ex:
            try:
                echo0(str(ex))
                thisOpenCmd = "open"
                print("  - thisOpenCmd={}...".format(thisOpenCmd))
                return BLink._run_parts([thisOpenCmd, Exec], check=True)
            except OSError as ex2:
                echo0(str(ex2))
                thisOpenCmd = "xdg-launch"
                print("  - trying {}...".format(thisOpenCmd))
                return BLink._run_parts([thisOpenCmd, Exec], check=True)
        except subprocess.CalledProcessError as ex:
            # raise subprocess.CalledProcessError(
            #     "{} couldn't open the Exec target: \"{}\""
            #     "".format(thisOpenCmd, Exec)
            # )
            raise ex
        return 1  # This should never happen.

    def _choose_app(self, path):
        '''
        Choose an application if either it isn't a blnk file at all or
        Type is "File" (only use _run instead of _choose_app if Type is
        Application).
        '''
        global settings
        cwd = None
        # cwd = os.path.dirname(os.path.realpath(self.path))
        # print('  - set cwd="{}"'.format(cwd))
        # ^ Leave cwd as None since it should only be set by
        #   the 'Path' key of the shortcut.
        print("  - choosing app for \"{}\"".format(path))
        app = "geany"
        # If you set blnk to handle unknown files:
        more_parts = []
        orig_app = app
        cmd_parts = None
        more_missing = []
        associations = settings['file_type_associations']
        for dotExt, args in associations.items():
            if path.lower().endswith(dotExt):
                if isinstance(args, list):
                    app = args[0]
                    more_parts = args[1:]
                else:
                    app = args
                if which(app) is not None:
                    break
                else:
                    more_missing.append(app)
                # else keep looking for other options
                cmd_parts = [app] + more_parts + [path]

        # shlex.split is NOT necessary since _choose_app should
        # NOT run for executables (Type=Application).

        '''
        absPath = self.getAbs(path)
        if os.path.splitext(path)[1] == "" and os.access(absPath, os.X_OK):
            # app = path
            # more_parts = []
            cmd_parts =
        '''
        if which(app) is None:
            dotExt = os.path.splitext(path)[1]
            missing_msg = ""
            if len(more_missing) > 0:
                missing_msg = " (and any of: {})".format(more_missing)
            print('    Warning: "{}"{} is missing so {} will open {}.'
                  ''.format(app, missing_msg, orig_app, dotExt))
            app = orig_app
            more_parts = []
        if path.lower().endswith(".nja"):
            path = os.path.split(path)[0]
            # ^ With the -p option, Ninja-IDE will only open a directory
            #   (with or without an nja, but not the nja file directly).
        print("    - app={}".format(app))
        if cmd_parts is None:
            return BLink._run_parts(
                [app] + more_parts + [path],
                cwd=cwd,
            )
        else:
            return BLink._run_parts(
                cmd_parts,
                cwd=cwd,
                )

    def run(self):
        '''
        Run the BLink object.
        '''

        '''
        section = None
        section, Type = self.getBranch(BLink.NO_SECTION, 'Type')
        if Type is None:
            section = "[X-Blnk]"
            section, Type = self.getBranch(section, 'Type')
        echo1("[{}] Type={}".format(section, Type))
        '''
        Type = self.get('Type')  # ^ replaces all of the above
        echo1("Type={}".format(Type))

        if Type == "Link":
            url = self.get('URL')
            if url is None:
                raise SyntaxError("if Type={} then URL should be set.".format(Type))
            return BLink._run(url, Type)
        source_key = 'Exec'
        if self.get('Type') in ["Directory", "File"]:
            old_v = self.get('Exec')
            try_v = self.get('Path')
            if try_v is not None:
                # Created by a version of blnk >= 2022-11-02
                # 1:00 PM ET
                source_key = 'Path'

        execStr, err = self.getExec(key=source_key)
        # ^ Adds single quotes as necessary!
        # ^ Makes the path absolute
        if err is not None:
            echo0(err)
        if execStr is None:
            echo0("* Exec is None so choosing app...")
            return self._choose_app(self.path)
            # ^ Open the file itself since it is *not* in .blnk format.
        elif self.get("Type") == "File":
            execStr = not_quoted(execStr, key=source_key)
            echo0("* Type=File so choosing app...")
            return self._choose_app(execStr)
        # else only Run the execStr itself if type is Application!
        # - However, _run detects Type=Directory and handles that.
        # echo0("Trying _run...")
        cwd, PathErr = self.getExec(key='Path')
        # ^ Resolves relative paths, but also adds quotes, so:
        cwd = not_quoted(cwd)
        if PathErr is not None:
            echo0(PathErr)
        else:
            echo1("* there is no PathErr from getExec(key='cwd') in run.")
            echo1('  - cwd="{}"'.format(cwd))
        return BLink._run(execStr, self.get('Type'), cwd=cwd)
        # ^ _run should split parts (for relative, see getExec)
        # ^ Type is detected automatically.


dtLines = [
    "[Desktop Entry]",
    "Exec={}".format(myBinPath),
    "MimeType=text/blnk;",
    "NoDisplay=true",
    "Name=blnk",
    "Type=Application",
]
'''
^ dtLines is for generating an XDG desktop file for launching blnk itself so
  that blnk appears in the "Choose Applicaton" menu for opening a .blnk file,
  and doesn't represent the content of a .blnk file itself (though blnk format
  is based on the XDG desktop shorcut format).
'''
#
#   Don't set NoDisplay:true or it can't be seen in the "Open With" menu
#   such as in Caja (MATE file explorer)
#   - This is for blnk itself. For blnk files, see blnkTemplate.


def usage():
    print(__doc__)


def create_icon():
    print("* checking for \"{}\"".format(dtPath))
    if not os.path.isfile(dtPath):
        print("* writing \"{}\"...".format(dtPath))
        if not os.path.isdir(SHORTCUTS_DIR):
            os.makedirs(SHORTCUTS_DIR)
        with open(dtPath, 'w') as outs:
            for line in dtLines:
                outs.write(line + "\n")
        if not platform.system == "Windows":
            print("  - installing...")
            iconCommandParts = ["xdg-desktop-icon", "install",
                                "--novendor"]
            cmdParts = iconCommandParts + [dtPath]
            try:
                BLink._run_parts(cmdParts)
            except subprocess.CalledProcessError:
                # os.remove(dtPath)
                # ^ Force automatically recreating the icon.
                echo0("{} failed.".format(cmdParts))
                echo0(str(cmdParts))


def run_file(path, options):
    '''
    Sequential arguments:
    options -- You must at least set:
        'interactive': Try to show a tk messagebox for errors if True.

    Returns:
    If OK return 0, otherwise another int.
    '''
    try:
        link = BLink(path)
        # ^ This path is the blnk file, not its target.
        link.run()
        # ^ init and run are in the same context in case construct
        #   fails.
        return 0
    except FileTypeError:
        pass
        # already handled by Blink
    except FileNotFoundError as ex:
        # echo0(get_traceback())
        showMsgBoxOrErr(
            "The file was not found: {} {}".format(ex, get_traceback()),
            try_gui=options['interactive'],
        )
    except Exception as ex:
        # msg = "Run couldn't finish: {}".format(ex)
        showMsgBoxOrErr(
            get_traceback(),
            try_gui=options['interactive'],
        )
    # ^ IF commenting bare Exception, the caller must show output.
    return 1


def create_shortcut_file(target, options, target_key='Exec'):
    '''
    Sequential arguments:
    options -- Define values for the shortcut using keys that are the same
        names as used in XDG shortcut format. You must at least set:
        'Terminal' (True will be changed to "true", False to "false"), 'Type',
        'interactive': Try to show a tk messagebox for errors if True.
        (Name will be generated from target's ending if None).

    Keyword arguments:
    target_key -- Set this to 'URL' if targtet is a URL.

    Returns:
    If OK return 0, otherwise another int.

    '''
    valid_target_keys = ['Exec', "URL"]
    if target_key not in valid_target_keys:
        raise ValueError("target_key is '{}' but should be among: {}"
                         "".format(target_key, valid_target_keys))
    if options.get('Name') is None:
        if target_key == "URL":
            raise ValueError("You must provide a 'Name' option for a URL.")
        if target.endswith(os.path.sep):
            target = target[:-len(os.path.sep)]
        # echo1('Using target: "{}"'.format(target))
        options["Name"] = os.path.splitext(os.path.split(target)[-1])[0]
        # ^ Also should be done to calculate options['Name'] before
        #   calling this function if done automatically.
    newName = options["Name"] + ".blnk"
    newPath = newName
    if options.get('Type') is None:
        raise KeyError("Type is required.")
    if options.get('Terminal') is None:
        raise KeyError(
            'Terminal (with value True, False, "true" or "false" is required'
        )
    if options['Terminal'] is True:
        options['Terminal'] = "true"
    elif options['Terminal'] is False:
        options['Terminal'] = "false"
    # ^ Use the current directory, so do not use the full path.
    mtime = None
    ctime = None
    # INFO: The included shortcut will redirect stderr (then show
    # the log at the end if not empty).
    if os.path.isfile(target) or os.path.isdir(target):
        echo1('Using target: "{}"'.format(target))
        mtime_ts = pathlib.Path(target).stat().st_mtime
        mtime = datetime.fromtimestamp(mtime_ts, tz=timezone.utc)
        ctime_ts = pathlib.Path(target).stat().st_ctime
        ctime = datetime.fromtimestamp(ctime_ts, tz=timezone.utc)
        # ^ stat raises FileNotFoundError if not os.path.exists
        # TODO: test both on mac, and if necessary use
        #   os.stat(target).st_birthtime "To get file creation time on Mac
        #   and some Unix based systems."
        #   -<https://pynative.com/python-file-creation-modification-datetime/>
        '''
        As per <https://blog.ganssle.io/articles/2019/11/utcnow.html
        :~:text=timestamp()%20method%20gives%20a,
        time%2C%20even%20if%20you%20originally>:
        tz=timezone.utc correctly (in Python 3 only?) makes the
        output utilize timezone. For example:
        str(mtime) output (during DST):
        2022-08-09 14:39:55.144246
        changes to:
        2022-08-09 18:39:55.144246+00:00
        (Note that the output of the GNU stat command uses a different
        notation:
        Modify: 2022-08-09 14:39:55.144246010 -0400
        )
        '''
    # else:
    #     echo1('Warning: The target does not exist: "{}"'
    #           ''.format(target))

    Exec_fmt = "{}"
    if os.path.exists(target) and (" " in target):
        Exec_fmt = '"{}"'

    if options['Type'] in ["Directory", "File"]:
        # In XDG desktop format:
        # - The file extension would be ".directory" for a directory
        # - There is no "File" type (Only Application, Link, and
        #   Directory are valid).
        # - The desktop-file-validate command can diagnose issues.
        # - See also "XDG specification issue" comment further up.
        content = fileOrDirTemplate.format(
            Type=options["Type"],
            Name=options["Name"],
            Path=Exec_fmt.format(target),
            mtime=mtime,
            ctime=ctime,
        )
    elif target_key == 'Exec':
        content = blnkTemplate.format(
            Type=options["Type"],
            Name=options["Name"],
            Exec=Exec_fmt.format(target),
            Terminal=options["Terminal"],
            mtime=mtime,
            ctime=ctime,
        )
    elif target_key == "URL":
        if options['Type'] != "Link":
            raise RuntimeError(
                "The type for target URL should be Link but is {}"
                "".format(options['Type'])
            )
        accessed = datetime.now(tz=timezone.utc)
        content = blnkURLTemplate.format(
            Type=options["Type"],
            Name=options["Name"],
            URL=target,
            Terminal=options["Terminal"],
            accessed=accessed,
        )
    else:
        raise NotImplementedError("target_key={}".format(target_key))
    # echo0(content)
    if os.path.exists(newPath):
        echo0("Error: {} already exists.".format(newPath))
        return 1
    with open(newPath, 'w') as outs:
        outs.write(content)
    print("* wrote \"{}\"".format(newPath))
    return 0


def main(args):
    # create_icon()
    if len(args) < 2:
        usage()
        raise ValueError(
            "Error: The first argument is the program but"
            " there is no argument after that. Provide a"
            " file path."
        )
    MODE_RUN = "run"
    MODE_CS = "create shortcut"
    mode = MODE_RUN
    path = None
    options = {}
    options["interactive"] = True
    options["Terminal"] = "false"
    for i in range(1, len(args)):
        arg = args[i]
        if arg == "-s":
            mode = MODE_CS
        elif arg == "--terminal":
            options["Terminal"] = "true"
        elif arg in ["--non-interactive", "-y"]:
            options["interactive"] = False
        elif arg == "--verbose":
            set_verbosity(1)
        elif arg == "--debug":
            set_verbosity(2)
        elif arg.startswith("--"):
            echo0('The argument "{}" is invalid.'.format(arg))
            return 1
        else:
            if path is None:
                path = arg
            elif options.get('Name') is None:
                options['Name'] = arg
                echo0('Name="{}"'.format(options['Name']))
            else:
                raise ValueError("The option \"{}\" is unknown and the"
                                 " path was already \"{}\""
                                 "".format(arg, path))
    if path is None:
        usage()
        echo0("Error: The path was not set (args={}).".format(args))
        return 1
    options["Type"] = None
    target_key = 'Exec'
    if os.path.isdir(path):
        options["Type"] = "Directory"
    elif os.path.isfile(path):
        options["Type"] = "File"
    elif is_url(path):
        options["Type"] = "Link"
        target_key = "URL"
        if options.get('Name') is None:
            echo1("got: {}".format(sys.argv))
            amp_msg = ('If the URL has an ampersand, quote the URL\n'
                       ' to prevent the URL from cutting off such as\n'
                       ' if that is not the complete URL you entered.'
                       ''.format(path))
            showMsgBoxOrErr(
                ('Error: Please provide a name for the shortcut'
                 ' after the URL\n "{}"\n ({}).'.format(path, amp_msg)),
                try_gui=options["interactive"],
            )
            return 1
    if options["Type"] is None:
        usage()
        showMsgBoxOrErr(
            "Error: The path \"{}\" is not a file or directory"
            " (args={}).".format(path, args),
            try_gui=options["interactive"],
        )
        return 1
    if mode == MODE_RUN:
        return run_file(path, options)
    elif mode == MODE_CS:
        # Create shortcut
        return create_shortcut_file(path, options, target_key=target_key)
    else:
        raise NotImplementedError("The mode \"{}\" is not known."
                                  "".format(mode))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
