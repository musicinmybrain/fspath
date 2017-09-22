# -*- mode: python; coding: utf-8 -*-
"""
Simple user interface via terminal (win & *nix)

This module is in a very early stage, don't use it!
"""
# pylint: disable=invalid-name, bad-continuation, wrong-import-position

# ==============================================================================
# imports
# ==============================================================================

import os
import sys
import re
import time

from textwrap import fill

CONSOLE_TYPE = None

if (sys.platform.startswith('linux')
    or sys.platform.startswith('darwin')
    or sys.platform.startswith('freebsd')):
    import tty     # pylint: disable=E0401
    import termios # pylint: disable=E0401
    CONSOLE_TYPE = 'tty'

elif sys.platform in ('win32', 'cygwin'):
    import msvcrt   # pylint: disable=E0401
    CONSOLE_TYPE = 'cmd'
else:
    raise NotImplementedError(
        'The platform %s is not supported yet' % sys.platform)

CTRL_C    = '\x03'
BS  = '\x08'
DEL = '\x7f'
CR  = '\r'


# ==============================================================================
def consoleDimension():
# ==============================================================================
    u"""Returns count of (row, columns) from current console

    .. hint:

       Since Win-CMD adds a newline if the last column is filled with a
       character it is recomended to use one column less.

    """

    # pylint: disable=broad-except
    rows, columns = 25, 80

    if CONSOLE_TYPE == 'cmd':
        try:
            rows, columns = consoleDimensionsWIN()
        except Exception:
            pass
    else:
        try:
            rows, columns = consoleDimensionsLinux()
        except Exception:
            pass
    try:
        rows = int(rows)
    except Exception:
        pass

    try:
        columns = int(columns)
    except Exception:
        pass

    return rows, columns

def consoleDimensionsLinux():
    u"""Returns count of (row, columns) from current console"""
    rows, columns = os.popen('stty size', 'r').read().split()
    return rows, columns

def consoleDimensionsWIN():
    u"""Returns count of (row, columns) from current console"""
    # pylint: disable=too-many-locals
    from ctypes import windll, create_string_buffer

    # stdin handle is -10
    # stdout handle is -11
    # stderr handle is -12

    h = windll.kernel32.GetStdHandle(-12)
    csbi = create_string_buffer(22)
    res = windll.kernel32.GetConsoleScreenBufferInfo(h, csbi)

    columns, rows = 80, 25
    if res:
        import struct
        (_bufx, _bufy, _curx, _cury, _wattr,
         left, top, right, bottom, _maxx, _maxy) = struct.unpack("hhhhHhhhhhh", csbi.raw)
        columns = right - left + 1
        rows    = bottom - top + 1

    return rows, columns

# ==============================================================================
class SimpleUserInterface(object):
# ==============================================================================

    """Simple console based user interface (win & *nix)"""

    ui_out = sys.stdout
    ui_in  = sys.stdin

    rst_indent = '    '
    rst_levels = {'part' : '=', 'chapter' : '=', 'section' : '-', 'subsection' : '~'}

    def __init__(self, cli=None):
        if cli is not None:
            self.cli    = cli
            self.ui_out = cli.OUT

    if CONSOLE_TYPE == 'tty':
        @classmethod
        def getchr(cls):
            "Get a single unicode character on Linux & Unix."
            f = cls.ui_in.fileno()
            m = termios.tcgetattr(f)
            try:
                tty.setraw(f)
                #ch = codecs.getreader(cls.ui_in.encoding)(cls.ui_in).read(1)
                ch = cls.ui_in.read(1)
                if ch == CTRL_C:
                    raise KeyboardInterrupt
            finally:
                termios.tcsetattr(f, termios.TCSADRAIN, m)
            return ch

    elif CONSOLE_TYPE == 'cmd':
        @classmethod
        def getchr(cls):
            "Get a single unicode character on Windows."
            while msvcrt.kbhit():
                # clear keyboard buffer
                msvcrt.getwch()
            ch = msvcrt.getwch()
            if ch in u'\x00\xe0':
                # arrow or function key pressed
                ch = msvcrt.getwch()
            if ch == CTRL_C:
                raise KeyboardInterrupt
            return ch


    @classmethod
    def get_input(cls, count=None, echo=True, valid_chars=r'.', stop_char=CR):
        u"""read input from UI"""
        ret_val = u""
        c = 0
        while count is None or count > c:
            is_valid = False
            while not is_valid:
                ch = cls.getchr()
                if ch == CR or valid_chars is None:
                    is_valid = True
                else:
                    is_valid = bool(re.compile(valid_chars).match(ch))
            c += 1
            if ch == stop_char:
                break
            ret_val += ch
            if echo:
                cls.write(ch)
        return ret_val

    @classmethod
    def write(cls, msg):
        u"""write to UI"""
        #cls.ui_out.write(msg.decode(cls.ui_out.encoding))
        cls.ui_out.write(msg)
        cls.ui_out.flush()

    @classmethod
    def echo(cls, msg):
        u"""write line to UI"""
        cls.write(msg + '\n')

    @classmethod
    def rst_title(cls, title, level='chapter'):
        u"""write reST formated title to UI

        :param str title: section's title
        :param str level: section's structural level [part,chapter,section,subsection]
        """
        markup = cls.rst_levels.get(level, None)
        if markup is None:
            raise ValueError("unknown section level '%s'" % level)
        title  = title.strip()
        markup = markup * len(title)
        if level == 'part':
            cls.write(u'\n' + markup)
        cls.write(u'\n' + title)
        cls.write(u'\n' + markup + u'\n\n')

    @classmethod
    def rst_p(cls, text, level=0):
        u"""write reST formated paragraph to UI

        :param int level: indentaion level
        """
        text = re.sub(r'\s+', ' ', text).strip()
        p = fill(text
                 , width                = cls._get_usable_line_size()
                 , initial_indent       = cls.rst_indent * level
                 , subsequent_indent    = cls.rst_indent * level
                 , fix_sentence_endings = True )
        cls.write(p.strip() + u'\n\n')

    @classmethod
    def rst_table(cls, rows, *fmt, **kwargs):
        u"""write reST formated table to UI

        Uses :py:class:`ASCIITableFormatter` for output. The argument ``*fmt``
        is a list of tuple.

        :param list rows: iterable type of dictionaries with the col/value
        :param list *fmt: iterable type of tuples to format the table
        :param int level: indentaion level

        .. code-block:: python
           SUI.rst_table(
               test_rows
               # <col-title>, <format sting>, <attribute name>
               , ("Foo",      "%-12s",        "foo")
               , ("Bar",      "%-30s",        "bar"))

        """
        level = kwargs.get('level', 0) # tribute to py2 keyword-arguments
        table = ASCIITableFormatter(*fmt)
        for line in table(rows).strip().split('\n'):
            if line:
                cls.write('    ' * level)
            cls.write(line + '\n')
        cls.write('\n\n')

    @classmethod
    def _get_usable_line_size(cls):
        l = consoleDimension()[1]
        if CONSOLE_TYPE == 'cmd':
            # Since Win-CMD adds a newline if the last column is filled with a
            # character it is recomended to use one column less.
            l -= 1
        return l

    @classmethod
    def fill_line(cls, fill_char=' '):
        u"""console, fill line with ``fill_char`` (default ' ')"""
        line_size = cls._get_usable_line_size()
        cls.write(CR)
        cls.write(fill_char[0] * line_size)
        cls.write(CR)

    @classmethod
    def wait_key(cls):
        u"""wait until key pressed"""
        msg = '** press any [KEY] to continue **'
        _len = len(msg)
        cls.write(msg)
        _i = cls.get_input(count=1, echo=False)
        cls.write(BS * _len)
        cls.write(' ' * _len)
        cls.write(BS * _len)

    @classmethod
    def ask_choice(cls, msg, choices, default=0):
        u"""Take a choice from a list via UI"""

        for i in enumerate(choices, 1):
            cls.echo(u"%2d. %s" % i)
        i = None
        while i is None:
            cls.write("%s [%s] " % (msg, default+1))
            c = len(choices)
            u = cls.get_input(count=len(str(c)), valid_chars=r'\d')
            if u == u'':
                i = default
                cls.write(str(i+1))
            try:
                i = int(u) - 1
                if i < 0 or i > c:
                    i = None
                    cls.write(' <-- ')
                    cls.write('ERROR: invalid choice.')
                    time.sleep(1)
                    cls.fill_line()
            except ValueError:
                pass
        return choices[i]

    @classmethod
    def ask(cls, msg, default=None, count=None, echo=True, valid_chars=r'.', stop_char=CR):
        u"""Ask via UI"""
        cls.write("%s " % msg)
        if default is not None:
            cls.write("[%s] " % default)
        answer = cls.get_input(count=count, echo=echo, valid_chars=valid_chars,
                               stop_char=stop_char)
        if not answer:
            answer = default
            cls.write(str(default))
        return answer

    YES = True
    NO  = False

    @classmethod
    def ask_yes_no(cls, msg, default='y'):
        u"""Ask Yes/No [YN] via UI

        Returns ``True`` for *Yes* and ``False`` for *No*
        """
        if default not in 'yn':
            raise ValueError('unknown value for default, use "n" or "y"')
        cls.write('%s %s ' % (msg, {'y':'[Y/n]', 'n':'[y/N]'}[default]))
        answer = cls.get_input(count=1, echo=True,  valid_chars=r'[YNyn]')
        if not answer:
            answer = default
            cls.write(str(default))
        else:
            answer = answer.lower()
        return {'y' : cls.YES, 'n' : cls.NO}[answer]


SUI = SimpleUserInterface()

# ==============================================================================
class ASCIITableFormatter(object):
# ==============================================================================

    """Simple ASCII table formatter

    .. code-block:: python

       rows = [  {'foo': 'foo row 1', 'bar': 'bar row 1'}
                 , {'foo': 'foo row 2', 'bar': 'bar row 2'} ]

       table = ASCIITableFormatter(
           # <col-title>, <format sting>, <attribute name>
           ("Foo",   "%-12s", "foo")
           , ("Bar", "%-30s", "bar"))
       SUI.echo(table(rows))

    .. code-block:: rst

       ============ ==============================
       Foo          Bar
       ============ ==============================
       foo row 1    bar row 1
       foo row 2    bar row 2
       ============ ==============================
    """

    table_start,     table_end    = "",   ""
    head_start,      head_end     = "\n", ""
    col_head_start,  col_head_end = "",   " "
    row_start,       row_end      = "\n", ""
    col_start,       col_end      = "",   " "
    sep_start,       sep_end      = "",   " "
    sep_line = "="

    def __init__(self, *cols):
        self.coldef = cols

    def get_value(self, attr, row, default='?'):  # pylint: disable=no-self-use
        u"""get value from col (attr) and row"""
        val = default
        if hasattr(row, "__getitem__"):
            val = row.get(attr, default)
        else:
            val = getattr(row, attr, None)
        return val

    def escape(self, value): # pylint: disable=no-self-use
        u"""escape value"""
        return value

    def __call__(self, rows):
        out = u""
        out += self.table_start

        sep = u''
        if self.sep_line:
            sep += self.head_start
            for headline, fmt, attr in self.coldef:
                sep += self.sep_start
                sep += self.sep_line * len(fmt % 1)
                sep += self.sep_end
            sep += self.head_end

        # head-top separator line
        out += sep

        # headline
        out += self.head_start
        for headline, fmt, attr in self.coldef:
            out += self.col_head_start
            out += headline.ljust(len(fmt % 1))
            out += self.col_head_end
        out += self.head_end

        # head-bottom separator line
        out += sep

        # render rows
        for row in rows:
            out += self.row_start
            for headline, fmt, attr in self.coldef:
                out += self.col_start
                val = self.get_value(attr, row)
                val = self.escape(val)
                out += fmt % val
                out += self.col_end
            out += self.row_end

        # bottom separator
        out += sep

        out += self.table_end
        return out

# ==============================================================================
class HTMLTableFormatter(ASCIITableFormatter):
# ==============================================================================

    """Simple HTML table formatter

    .. code-block:: python

       rows = [  {'foo': 'foo <row 1>', 'bar': 'bar <row 1>'}
                 , {'foo': 'foo <row 2>', 'bar': 'bar <row 2>'} ]

       table = HTMLTableFormatter(("Foo", "%s", "foo")
                                , ("Bar", "%s", "bar"))
       SUI.echo(table(rows))

    .. code-block:: html

       <table>
         <tr class='heading'>
           <th>Foo</th>
           <th>Bar</th>
         </tr>
         <tr>
           <td>foo &lt;row 1&gt;</td>
           <td>bar &lt;row 1&gt;</td>
         </tr>
         <tr>
           <td>foo &lt;row 2&gt;</td>
           <td>bar &lt;row 2&gt;</td>
         </tr>
       </table>
    """

    table_start, table_end        = "\n<table>",                "\n</table>"
    head_start,  head_end         = "\n  <tr class='heading'>", "\n  </tr>"
    col_head_start,  col_head_end = "\n    <th>",               "</th>"
    row_start,   row_end          = "\n  <tr>",                 "\n  </tr>"
    col_start,   col_end          = "\n    <td>", "</td>"
    sep_line = None
    ESCAPE = "<!--(set_escape)-->HTML<!--(end)-->\n#!"

    def escape(self, value):
        value = value.replace("&", "&amp;") # Must be done first!
        value = value.replace("<", "&lt;")
        value = value.replace(">", "&gt;")
        return value
