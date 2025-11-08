#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert vJASS+ into vJASS code
Python Version: 3.12
vJASS+ Version: 3.53

Author: choi-sw (escaco95@naver.com)

Change Log:
- 3.53: Added multi-language support
- 3.52: Added support for .j file import
- 3.51: Changed macro arguments to literal string
  - 3.511: Added support for global block alignment
- 3.50: Added support for dot in identifier names
  - 3.501: Removed support '->' operator for api(public) call syntax
  - 3.502: Fixed keyword processor bug which converts 'this' into 'th=='
- 3.45: Added 'none' keyword for zero value
  - 3.451: Removed integer null initialization support
- 3.44: Added 'is, is not' operators for comparison
  - 3.441: Added 'pass' and 'exit' keywords as alias of 'return'
- 3.43: Added '->' operator for api(public) call syntax
- 3.42: Added '!!' operator for boolean negation
- 3.41: Added support for .jpcon, .jpsys, .jpdat, .jplib file extensions
- 3.40: Changed import syntax to use quotes
- 3.31: Added alias type support
  - 3.311: integers can be initialized with null(=0) expression
- 3.30: Changed variable definition syntax
  - 3.301: Added ~ operator for const variable definition
- 3.20: Added macro block (macro myMacro:) support
  - 3.201: fixed macro argument parsing with commas in quotes
- 3.14: Added data block (data:) syntax
  - 3.144: can omit type extends (default is array)
  - 3.143: syntax error exactly picks the line number from now on
  - 3.142: fixed redundant parenthesis creation in f-string
  - 3.141: fixed compilation process, source-by-source to step-by-step
- 3.13: Added multi-line in single line comment support
- 3.12: Added break keyword support
- 3.11: Added in-line comment support
  - 3.111: fixed parser failure on exitwhen keyword
- 3.10: Added f-string (f"{}") support
  - 3.101: Changed token processing algorithm, generates EOF empty line gracefully
  - 3.102: Fixed parser failure on excessive spaces after function colon
- 3.04: Added system block (system:) syntax
- 3.03: Added modifier block (api:/global:) syntax
- 3.02: Added mass import (.*/.**) syntax
  - 3.021: Fixed variable syntax regex including library/scope/content
- 3.00: Initial release
"""

import os
import re
import sys
import uuid
import inspect


class DslSyntaxError(Exception):
    """
    Exception raised for syntax errors in the DSL.
    """

    def __init__(self, filePath: str, lineCursor: int, lineText: str, message: str):
        super().__init__(message)
        self.filePath = filePath
        self.lineCursor = lineCursor
        self.lineText = lineText
        self.message = message

    def __str__(self):
        if self.lineCursor:
            return f'File "{self.filePath}", line {self.lineCursor + 1}\n{self.message}'
        else:
            return f'File "{self.filePath}"\n{self.message}'


def generateUUID():
    """
    Generate a 16 width uppercase UUID.
    """
    return str(uuid.uuid4()).replace('-', '').upper()[:16]


def normalizePath(sourceFilePath):
    return os.path.abspath(sourceFilePath.replace('\\', '/'))


def convertToIdentifierOrNone(text: str) -> str | None:
    """
    Convert unknown format text into PascalCase format.
      * If the result is invalid identifier, return None.
    Example:
    - my_library -> MyLibrary
      * underscores are word separators
    - my-library -> MyLibrary
      * hyphens are word separators
    - my.library -> MyLibrary
      * dots are word separators
    - my library -> MyLibrary
      * spaces are word separators
    - MyLibrary -> MyLibrary
      * it is single word and starts with capital letter
      * so do nothing
    - myLibrary -> MyLibrary
      * each word must start with capital letter
      * so capitalize the first letter of each word
    """
    # split by underscore, hyphen, dot, space
    words = re.split(r'[_\-\.\s]+', text)
    # capitalize each word
    words = [word.capitalize() for word in words]
    # join words
    result = ''.join(words)
    # check if result is a valid identifier
    if not re.match(r'^[A-Z][a-zA-Z0-9]*$', result):
        return None
    return result


class ProcessEnvironment:
    def __init__(self):
        self.sourceGroup = {}

        self.arguments = {}
        self.libraries = []
        self.datalibs = []
        self.systems = []

        self.macros = {}
        # self.functions = {}

        self.sourcePath = None
        self.sourceLines = []
        self.nextLines = []

    def containsArgument(self, argument: str) -> bool:
        return argument in self.arguments and self.arguments[argument] is not None


"""
:'######:::'#######::'##::::'##:'########::'####:'##:::::::'########:
'##... ##:'##.... ##: ###::'###: ##.... ##:. ##:: ##::::::: ##.....::
 ##:::..:: ##:::: ##: ####'####: ##:::: ##:: ##:: ##::::::: ##:::::::
 ##::::::: ##:::: ##: ## ### ##: ########::: ##:: ##::::::: ######:::
 ##::::::: ##:::: ##: ##. #: ##: ##.....:::: ##:: ##::::::: ##...::::
 ##::: ##: ##:::: ##: ##:.:: ##: ##::::::::: ##:: ##::::::: ##:::::::
. ######::. #######:: ##:::: ##: ##::::::::'####: ########: ########:
:......::::.......:::..:::::..::..:::::::::....::........::........::
"""


def compile():
    # if there is no argument, print usage
    if len(sys.argv) < 2:
        print("Usage: python vjassp.py <source_path>")
        print("Usage: python vjassp.py <source_path> DEBUG REFORGED JN")
        sys.exit(1)

    # use the first argument as the source path
    entryPath = normalizePath(sys.argv[1])

    # use other arguments as the options tag
    options = sys.argv[2:]

    # scan all classes in __file__ that contains static method process(env) function
    # and add them to the tokenProcessors list
    # get all classes in this file
    preprocessors = []
    processors = []
    classes = [cls for name, cls in globals().items(
    ) if inspect.isclass(cls) and cls.__module__ == __name__]
    # get all static methods in the class that contains process(env) function
    for cls in classes:
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if name == 'process' and method.__code__.co_argcount == 1:
                processors.append(method)
            elif name == 'preprocess' and method.__code__.co_argcount == 1:
                preprocessors.append(method)

    # Step 1: Initialize the source group
    env = ProcessEnvironment()
    env.sourceGroup = {
        entryPath: {
            'preprocessed': False
        }
    }
    env.arguments = {}
    for option in options:
        # if option format is a=b, split it into a and b
        if '=' in option:
            option = option.split('=')
            # option name is option[0], option value is other parts joined by '='
            env.arguments[option[0]] = '='.join(option[1:])
        else:
            # else, set the option as True
            env.arguments[option] = True

    # print env
    print(f'Environment:')
    print(f'  Source Path: "{entryPath}"')
    print(f'  Arguments: {env.arguments}')
    print(f'  Preprocessors: {len(preprocessors)}')
    for index, preprocessor in enumerate(preprocessors):
        print(f'    {preprocessor.__qualname__}() ({index + 1})')
    print(f'  Processors: {len(processors)}')
    for index, processor in enumerate(processors):
        print(f'    {processor.__qualname__}() ({index + 1})')

    # Step 1.9: Preprocess all source files
    vjassLines = []
    while True:
        # Step 1.91: Find all source files that are not preprocessed
        sourceFiles = [path for path,
                       info in env.sourceGroup.items() if not info.get('preprocessed', False)]
        if not sourceFiles:
            break

        # Step 1.92: Preprocess each source file
        for sourcePath in sourceFiles:
            env.sourcePath = sourcePath
            env.sourceLines = []
            # Read the source file
            with open(sourcePath, 'r', encoding='utf-8') as file:
                # Preprocessing by file extension
                # - .j : normal vJASS file
                # - .jp : normal vJASS+ file
                # - .jpcon : vJASS+ content file
                # - .jpsys : vJASS+ system file
                # - .jpdat : vJASS+ data file
                # - .jplib : vJASS+ library file
                #   * try to convert filename into proper identifier(snake_case to PascalCase)
                #   * if fails, it will be converted into anonymous content block
                #       * if it was not content file, an error will be raised
                #   * append indentation to each line
                prefixLines = []
                indentation = ''

                try:
                    if sourcePath.endswith('.j'):
                        # normal vJASS file, add to non-compiled source directly
                        lines = file.read().splitlines()
                        vjassLines += lines
                        # mark as preprocessed
                        env.sourceGroup[sourcePath]['preprocessed'] = True
                        env.sourceGroup[sourcePath]['sourcelines'] = []
                        continue
                    elif sourcePath.endswith('.jpcon'):
                        blockName = os.path.splitext(
                            os.path.basename(sourcePath))[0]
                        blockName = convertToIdentifierOrNone(blockName)
                        if blockName is None:
                            prefixLines.append(f'content:')
                        else:
                            prefixLines.append(f'content {blockName}:')
                        indentation = '    '
                    elif sourcePath.endswith('.jpsys'):
                        blockName = os.path.splitext(
                            os.path.basename(sourcePath))[0]
                        blockName = convertToIdentifierOrNone(blockName)
                        if blockName is None:
                            raise DslSyntaxError(
                                sourcePath, 0, '', f'System file name must be a valid identifier: "{os.path.basename(sourcePath)}"')
                        prefixLines.append(f'system {blockName}:')
                        indentation = '    '
                    elif sourcePath.endswith('.jpdat'):
                        blockName = os.path.splitext(
                            os.path.basename(sourcePath))[0]
                        blockName = convertToIdentifierOrNone(blockName)
                        if blockName is None:
                            raise DslSyntaxError(
                                sourcePath, 0, '', f'Data file name must be a valid identifier: "{os.path.basename(sourcePath)}"')
                        prefixLines.append(f'data {blockName}:')
                        indentation = '    '
                    elif sourcePath.endswith('.jplib'):
                        blockName = os.path.splitext(
                            os.path.basename(sourcePath))[0]
                        blockName = convertToIdentifierOrNone(blockName)
                        if blockName is None:
                            raise DslSyntaxError(
                                sourcePath, 0, '', f'Library file name must be a valid identifier: "{os.path.basename(sourcePath)}"')
                        prefixLines.append(f'library {blockName}:')
                        indentation = '    '
                except DslSyntaxError as e:
                    print(f'Syntax Error (most recent call last):')
                    print(f'  {e}')
                    sys.exit(1)

                # add prefix lines (as fixed line number 0)
                for prefixLine in prefixLines:
                    env.sourceLines.append(
                        {'tags': {}, 'cursor': 0, 'line': prefixLine})

                # append source lines with indentation
                env.sourceLines += [{'tags': {}, 'cursor': sourceCursor, 'line': f'{indentation}{sourceLine}'}
                                    for sourceCursor, sourceLine in enumerate(file.read().splitlines())]

            # Preprocess each preprocessor
            try:
                for preprocessor in preprocessors:
                    env.nextLines = []
                    preprocessor(env)
                    env.sourceLines = env.nextLines
            except DslSyntaxError as e:
                print(f'Syntax Error (most recent call last):')
                print(f'  {e}')
                sys.exit(1)
            except Exception as e:
                raise e

            # mark as preprocessed
            env.sourceGroup[sourcePath]['preprocessed'] = True
            env.sourceGroup[sourcePath]['sourcelines'] = env.sourceLines

    # print post compile environment
    print(f'  Imported files: {len(env.sourceGroup)}')
    for index, importPath in enumerate(env.sourceGroup.keys()):
        print(f'    File "{importPath}" ({index + 1})')
    # print all macros
    print(f'  Macros: {len(env.macros)}')
    for index, macroName in enumerate(env.macros.keys()):
        macroInfo = env.macros[macroName]
        print(f'    {macroName} ({index + 1})')

    # Step 2: Compile until all source files are compiled
    sourceFiles = [path for path, info in env.sourceGroup.items()]
    if sourceFiles:
        # Step 2.1: compile each source file
        for tokenProcessor in processors:
            for sourcePath in sourceFiles:
                env.sourcePath = sourcePath
                env.sourceLines = env.sourceGroup[sourcePath]['sourcelines']

                try:
                    env.nextLines = []
                    tokenProcessor(env)
                    env.sourceLines = env.nextLines
                except DslSyntaxError as e:
                    print(f'Syntax Error (most recent call last):')
                    print(f'  {e}')
                    sys.exit(1)
                except Exception as e:
                    raise e

                env.sourceGroup[sourcePath]['sourcelines'] = env.sourceLines

    # Step 2.9: merge all source files into one
    finalLines = []
    for sourcePath in sourceFiles:
        # add the source lines to the final lines
        for sourceLine in env.sourceGroup[sourcePath]['sourcelines']:
            finalLines.append(sourceLine['line'])

    # Step 3: Post compile
    # Step 3.1: resolve library and system block dependency
    if env.systems or env.datalibs:
        # if there is any system, add the system library
        if env.libraries:
            finalLines.append(
                f'library VJPLIBS requires {", ".join(env.libraries)}')
        else:
            finalLines.append(f'library VJPLIBS')
        finalLines.append(f'endlibrary')
    if env.systems:
        # if there is any data, add the data library
        if env.datalibs:
            finalLines.append(
                f'library VJPDATA requires {", ".join(env.datalibs)}')
        else:
            finalLines.append(f'library VJPDATA requires VJPLIBS')
        finalLines.append(f'endlibrary')

    # Step 4: finalize the source file
    # Step 4.1: add raw vjass lines
    if vjassLines:
        finalLines += vjassLines
    # Step 4.2: append empty line if the last line is not empty
    if not finalLines or not finalLines[-1].endswith('\n'):
        finalLines.append('')

    # write the final text to a file with same directory with .j extension
    finalPath = os.path.splitext(entryPath)[0] + '.j'
    with open(finalPath, 'w', encoding='utf-8') as file:
        file.write('\n'.join(finalLines))
    print(f'Compiled:')
    print(f'  File "{finalPath}"')


"""
::::::::::'######:::'#######::'##::::'##:'##::::'##:'########:'##::: ##:'########:
:::::::::'##... ##:'##.... ##: ###::'###: ###::'###: ##.....:: ###:: ##:... ##..::
::::::::: ##:::..:: ##:::: ##: ####'####: ####'####: ##::::::: ####: ##:::: ##::::
'#######: ##::::::: ##:::: ##: ## ### ##: ## ### ##: ######::: ## ## ##:::: ##::::
........: ##::::::: ##:::: ##: ##. #: ##: ##. #: ##: ##...:::: ##. ####:::: ##::::
::::::::: ##::: ##: ##:::: ##: ##:.:: ##: ##:.:: ##: ##::::::: ##:. ###:::: ##::::
:::::::::. ######::. #######:: ##:::: ##: ##:::: ##: ########: ##::. ##:::: ##::::
::::::::::......::::.......:::..:::::..::..:::::..::........::..::::..:::::..:::::
"""


class TokenComment:
    @staticmethod
    def preprocess(env: ProcessEnvironment) -> None:
        multiCommentBlock = False
        for sourceLine in env.sourceLines:
            sourceLineText = sourceLine['line']
            # multi-line comment block
            match = re.match(r'^\s*"""\s*$', sourceLineText)
            if match:
                multiCommentBlock = not multiCommentBlock
                continue
            if multiCommentBlock:
                continue
            # multi-in-line comment
            match = re.match(r'^\s*\"\"\".*?\"\"\"\s*$', sourceLineText)
            if match:
                continue
            # single-line comment
            match = re.match(r'^\s*#.*$', sourceLineText)
            if match:
                continue
            # empty line
            match = re.match(r'^\s*$', sourceLineText)
            if match:
                continue
            # in-line comment
            match = re.match(
                r'^(?P<code>.*?)(?P<comment>#[^\'\"]*)$', sourceLineText)
            if match:
                code = match.group('code')
                env.nextLines.append(
                    {'tags': sourceLine['tags'], 'cursor': sourceLine['cursor'], 'line': code})
                continue
            # anything else
            env.nextLines.append(sourceLine)


"""
:::::::::'####:'##::::'##:'########:::'#######::'########::'########:
:::::::::. ##:: ###::'###: ##.... ##:'##.... ##: ##.... ##:... ##..::
:::::::::: ##:: ####'####: ##:::: ##: ##:::: ##: ##:::: ##:::: ##::::
'#######:: ##:: ## ### ##: ########:: ##:::: ##: ########::::: ##::::
........:: ##:: ##. #: ##: ##.....::: ##:::: ##: ##.. ##:::::: ##::::
:::::::::: ##:: ##:.:: ##: ##:::::::: ##:::: ##: ##::. ##::::: ##::::
:::::::::'####: ##:::: ##: ##::::::::. #######:: ##:::. ##:::: ##::::
:::::::::....::..:::::..::..::::::::::.......:::..:::::..:::::..:::::
"""


class TokenImport:
    # supported file extensions
    SUPPORTED_EXTENSIONS = ['.j', '.jp',
                            '.jpcon', '.jpsys', '.jpdat', '.jplib']

    @staticmethod
    def __is_importable_file(filePath: str) -> bool:
        # check if vjass-plus supports the file extension
        return any(filePath.endswith(ext) for ext in TokenImport.SUPPORTED_EXTENSIONS)

    @staticmethod
    def preprocess(env: ProcessEnvironment) -> None:
        for sourceCursor, sourceLine in enumerate(env.sourceLines):
            # single-line import statement
            match = re.match(
                r'^\s*(?:when\s+(?P<when>[a-zA-Z0-9_.-]+)\s+)?import\s+\"(?P<import>[^\"]+?)(?P<mass>(/\*|/\*\*))\"\s*$', sourceLine['line'])
            if match:
                # check when statement
                importWhen = match.group('when')
                if importWhen is not None and not env.containsArgument(importWhen):
                    # if when statement is not in arguments, skip this import statement
                    continue

                importPath = match.group('import').replace('\\', '/')
                importPath = os.path.join(
                    os.path.dirname(env.sourcePath), importPath)
                importPath = normalizePath(importPath)

                importMass = match.group('mass')
                importPaths = []
                # if import ends does not ends with /* or /**, it is a single file import
                if not importMass:
                    importPaths.append(importPath)
                elif importMass == '/*':
                    for root, dirs, files in os.walk(importPath):
                        for file in files:
                            if TokenImport.__is_importable_file(file):
                                # normalize path
                                file = normalizePath(
                                    os.path.join(root, file))
                                importPaths.append(file)
                elif importMass == '/**':
                    # double star import = recursive import
                    recursiveDirs = [importPath]
                    while recursiveDirs:
                        currentDir = recursiveDirs.pop()
                        for root, dirs, files in os.walk(currentDir):
                            for file in files:
                                if TokenImport.__is_importable_file(file):
                                    # normalize path
                                    file = normalizePath(
                                        os.path.join(root, file))
                                    importPaths.append(file)
                            # add subdirs to the list
                            for dir in dirs:
                                recursiveDirs.append(
                                    os.path.join(root, dir))

                # add import paths to the source group
                for importPath in importPaths:
                    if importPath not in env.sourceGroup:
                        # if file not exists, raise syntax error
                        if not os.path.exists(importPath):
                            raise DslSyntaxError(
                                env.sourcePath, sourceLine['cursor'], sourceLine, f'No such File "{importPath}"')
                        # add to the source group
                        env.sourceGroup[importPath] = {
                            'preprocessed': False,
                        }
                continue
            # anything else
            env.nextLines.append(sourceLine)


"""
:::::::::'##::::'##::::'###:::::'######::'########:::'#######::
::::::::: ###::'###:::'## ##:::'##... ##: ##.... ##:'##.... ##:
::::::::: ####'####::'##:. ##:: ##:::..:: ##:::: ##: ##:::: ##:
'#######: ## ### ##:'##:::. ##: ##::::::: ########:: ##:::: ##:
........: ##. #: ##: #########: ##::::::: ##.. ##::: ##:::: ##:
::::::::: ##:.:: ##: ##.... ##: ##::: ##: ##::. ##:: ##:::: ##:
::::::::: ##:::: ##: ##:::: ##:. ######:: ##:::. ##:. #######::
:::::::::..:::::..::..:::::..:::......:::..:::::..:::.......:::
"""


class TokenMacro:
    @staticmethod
    def preprocess(env: ProcessEnvironment) -> None:
        codeBlockInfoStack = []
        for sourceLine in env.sourceLines:
            # if code block stack is not empty and this line have same or less indent level
            # pop stack until the indent level is less than current indent level
            while codeBlockInfoStack:
                codeBlockInfo = codeBlockInfoStack[-1]
                match = re.match(r'^(?P<indent> *)', sourceLine['line'])
                indentLevel = len(match.group('indent')) // 4
                if indentLevel <= codeBlockInfo['indentLevel']:
                    codeBlockInfoStack.pop()
                else:
                    break

            # match macro-definable block (library/data/system/content)
            # for content, block may be anonymous
            match = re.match(
                r'^(?P<indent> *)(?P<blocktype>library|data|system|content)(?:\s+(?P<blockName>[a-zA-Z0-9_-][a-zA-Z0-9_.-]*))?\s*:\s*$', sourceLine['line'])
            if match:
                blockType = match.group('blocktype')
                blockName = match.group('blockName')
                if blockType == 'content' and blockName is None:
                    # make anonymous block name
                    blockName = f'VJPS{generateUUID()}'
                    # add name to the source line tag
                    sourceLine['tags']['name'] = blockName

                if blockName is None:
                    # if block name is not specified, raise syntax error
                    raise DslSyntaxError(
                        env.sourcePath, sourceLine['cursor'], sourceLine['line'], f'{blockType} name is not specified')

                codeBlockInfo = {
                    'indentLevel': len(match.group('indent')) // 4,
                    'cursor': len(env.nextLines),
                    'name': blockName,
                    'type': blockType,
                }
                codeBlockInfoStack.append(codeBlockInfo)
                env.nextLines.append(sourceLine)
                continue

            # match macro statement
            match = re.match(
                r'^(?P<indent> *)macro\s+(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)(\((?P<args>.*)\))?\s*:\s*$', sourceLine['line'])
            if match:
                # if there was no block, raise syntax error
                if not codeBlockInfoStack:
                    raise DslSyntaxError(
                        env.sourcePath, sourceLine['cursor'], sourceLine['line'], f'Macros must be defined in code block')

                # if last block was macro, raise syntax error
                if codeBlockInfoStack[-1]['type'] == 'macro':
                    raise DslSyntaxError(
                        env.sourcePath, sourceLine['cursor'], sourceLine['line'], f'Macros cannot be nested')

                # prepare to register macro
                blockName = codeBlockInfoStack[-1]['name']
                macroName = match.group('name')
                qualifiedMacroName = f'{blockName}.{macroName}'
                macroArgs = match.group('args')
                # if macro args becomes empty, set it to None
                if macroArgs is not None and macroArgs.strip() == '':
                    macroArgs = None
                if macroArgs is not None:
                    macroArgs = [arg.strip() for arg in re.split(
                        r',(?=(?:[^"]*"[^"]*")*[^"]*$)', macroArgs)]
                else:
                    macroArgs = []
                # if any args is invalid format
                for arg in macroArgs:
                    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', arg):
                        raise DslSyntaxError(
                            env.sourcePath, sourceLine['cursor'], sourceLine['line'], f'Invalid macro argument name "{arg}"')
                # if any arg is duplicated
                if len(macroArgs) != len(set(macroArgs)):
                    raise DslSyntaxError(
                        env.sourcePath, sourceLine['cursor'], sourceLine['line'], f'Duplication found in macro argument')
                # if macro name is already defined, raise syntax error
                if macroName in env.macros:
                    raise DslSyntaxError(
                        env.sourcePath, sourceLine['cursor'], sourceLine['line'], f'Macro "{macroName}"({qualifiedMacroName}) is already defined')
                # add macro to the macro list
                env.macros[qualifiedMacroName] = {
                    'args': macroArgs,
                    'indentLevel': 1 + len(match.group('indent')) // 4,
                    'bodyLines': [],
                }
                # stack the macro block
                codeBlockInfo = {
                    'indentLevel': len(match.group('indent')) // 4,
                    'cursor': len(env.nextLines),
                    'name': qualifiedMacroName,
                    'type': 'macro',
                }
                codeBlockInfoStack.append(codeBlockInfo)
                continue

            # if we are in macro block, add the line to the macro body
            if codeBlockInfoStack and codeBlockInfoStack[-1]['type'] == 'macro':
                macroName = codeBlockInfoStack[-1]['name']
                macroInfo = env.macros[macroName]

                # adjust indent level
                # trim 4 * macro indent level from beginning of the line
                unindentedLine = sourceLine['line'][4 *
                                                    macroInfo['indentLevel']:]

                macroInfo['bodyLines'].append(
                    {'tags': sourceLine['tags'], 'cursor': sourceLine['cursor'], 'line': unindentedLine})
                continue

            # anything else
            env.nextLines.append(sourceLine)

    @staticmethod
    def process(env: ProcessEnvironment) -> None:
        codeBlockInfoStack = []
        for sourceLine in env.sourceLines:
            # if code block stack is not empty and this line have same or less indent level
            # pop stack until the indent level is less than current indent level
            while codeBlockInfoStack:
                codeBlockInfo = codeBlockInfoStack[-1]
                match = re.match(r'^(?P<indent> *)', sourceLine['line'])
                indentLevel = len(match.group('indent')) // 4
                if indentLevel <= codeBlockInfo['indentLevel']:
                    codeBlockInfoStack.pop()
                else:
                    break

            # match macro-callable block (library/data/system/content)
            # for content, block may be anonymous
            match = re.match(
                r'^(?P<indent> *)(?P<blocktype>library|data|system|content)(?:\s+(?P<blockName>[a-zA-Z0-9_-][a-zA-Z0-9_.-]*))?\s*:\s*$', sourceLine['line'])
            if match:
                blockType = match.group('blocktype')
                blockName = match.group('blockName')
                if blockType == 'content' and blockName is None:
                    # get anonymous block name from the source line tag
                    blockName = sourceLine['tags']['name']

                codeBlockInfo = {
                    'indentLevel': len(match.group('indent')) // 4,
                    'cursor': len(env.nextLines),
                    'name': blockName,
                    'type': blockType,
                }
                codeBlockInfoStack.append(codeBlockInfo)
                env.nextLines.append(sourceLine)
                continue

            # match macro statement
            match = re.match(
                r'^(?P<indent> *)macro\s+(?P<name>[a-zA-Z_][a-zA-Z0-9_.]*)(\((?P<args>.*)\))?\s*$', sourceLine['line'])
            if match:
                # if there was no block, raise syntax error
                if not codeBlockInfoStack:
                    raise DslSyntaxError(
                        env.sourcePath, sourceLine['cursor'], sourceLine['line'], f'Macros must be defined in code block')

                # find macro info from environment
                blockName = codeBlockInfoStack[-1]['name']
                macroIndent = match.group('indent')
                macroName = match.group('name')
                macroArgs = match.group('args')
                # if macro args becomes empty, set it to None
                if macroArgs is not None and macroArgs.strip() == '':
                    macroArgs = None

                if macroArgs is not None:
                    macroArgs = [arg.strip() for arg in re.split(
                        r',(?=(?:[^"]*"[^"]*")*[^"]*$)', macroArgs)]
                else:
                    macroArgs = []

                qualifiedMacroName = f'{blockName}.{macroName}'

                # user may put full qualified name in macroName so we need to check first
                if macroName not in env.macros:
                    # if macro name is not found, check if it is full qualified name
                    if qualifiedMacroName not in env.macros:
                        raise DslSyntaxError(
                            env.sourcePath, sourceLine['cursor'], sourceLine['line'], f'Macro "{macroName}"({qualifiedMacroName}) is not defined')
                    else:
                        macroName = qualifiedMacroName

                # get macro info
                macroInfo = env.macros[macroName]
                macroInfoArgs = macroInfo['args']
                macroInfoBodyLines = macroInfo['bodyLines']

                # check arguments
                # -- argument count must be same
                if len(macroInfoArgs) != len(macroArgs):
                    raise DslSyntaxError(
                        env.sourcePath, sourceLine['cursor'], sourceLine['line'], f'Macro "{macroName}"({qualifiedMacroName}) argument count mismatch: {len(macroInfoArgs)} != {len(macroArgs)}')

                # convert string input into code fragment
                # e.g) "arg1" -> arg1
                # e.g) "value=\"test value\"," -> value="test value",
                for index, arg in enumerate(macroArgs):
                    match = re.match(
                        r'^\s*"(.*)"\s*$', arg)
                    if match:
                        macroArgs[index] = match.group(1)

                # append macro body prepending indent
                macroBodyCursor = sourceLine['cursor']
                for macroBodyLine in macroInfoBodyLines:
                    macroLineText = macroBodyLine['line']
                    macroLineText = f'{macroIndent}{macroLineText}'

                    # replace macro arguments with the arguments
                    # -- format: $argName$ -> argValue
                    macroLineText = re.sub(
                        r'\$(?P<argName>[a-zA-Z_][a-zA-Z0-9_]*)\$', lambda m: macroArgs[macroInfoArgs.index(m.group('argName'))], macroLineText)

                    env.nextLines.append(
                        {'tags': sourceLine['tags'], 'cursor': macroBodyCursor, 'line': macroLineText})
                continue

            # anything else
            env.nextLines.append(sourceLine)


"""
'##::::'##:'##::::'##:'##:::::::'########:'####:'##::::::::::'###::::'##::: ##::'######:::
 ###::'###: ##:::: ##: ##:::::::... ##..::. ##:: ##:::::::::'## ##::: ###:: ##:'##... ##::
 ####'####: ##:::: ##: ##:::::::::: ##::::: ##:: ##::::::::'##:. ##:: ####: ##: ##:::..:::
 ## ### ##: ##:::: ##: ##:::::::::: ##::::: ##:: ##:::::::'##:::. ##: ## ## ##: ##::'####:
 ##. #: ##: ##:::: ##: ##:::::::::: ##::::: ##:: ##::::::: #########: ##. ####: ##::: ##::
 ##:.:: ##: ##:::: ##: ##:::::::::: ##::::: ##:: ##::::::: ##.... ##: ##:. ###: ##::: ##::
 ##:::: ##:. #######:: ########:::: ##::::'####: ########: ##:::: ##: ##::. ##:. ######:::
..:::::..:::.......:::........:::::..:::::....::........::..:::::..::..::::..:::......::::
"""


class TokenUnicodeChar:
    """
    Originally, vJASS only supports ASCII characters.
    This processor converts non-ascii characters into ascii allowed characters.
    """
    # static dictionary to hold character mapping
    charMapping = {}
    charCounter = 1

    @staticmethod
    def conv(char: str) -> str:
        if char in TokenUnicodeChar.charMapping:
            return TokenUnicodeChar.charMapping[char]
        else:
            # generate new mapping
            mapping = f'U{TokenUnicodeChar.charCounter:03d}'
            TokenUnicodeChar.charMapping[char] = mapping
            TokenUnicodeChar.charCounter += 1
            return mapping

    @staticmethod
    def process(env: ProcessEnvironment) -> None:
        """
        WARN:
        - do not convert inside string literals
        - do not convert inside single quote literals
        """
        for sourceLine in env.sourceLines:
            lineText = sourceLine['line']
            newLineText = ''
            inString = False
            stringChar = None
            i = 0

            while i < len(lineText):
                char = lineText[i]

                if inString:
                    newLineText += char
                    # 이스케이프 문자 처리
                    if char == '\\' and i + 1 < len(lineText):
                        i += 1
                        newLineText += lineText[i]
                    elif char == stringChar:
                        inString = False
                        stringChar = None
                else:
                    if char in ('"', "'"):
                        inString = True
                        stringChar = char
                        newLineText += char
                    elif not (0x20 <= ord(char) <= 0x7E):
                        newLineText += TokenUnicodeChar.conv(char)
                    else:
                        newLineText += char

                i += 1

            env.nextLines.append(
                {'tags': sourceLine['tags'], 'cursor': sourceLine['cursor'], 'line': newLineText})


"""
::::::::::'######:::'##::::::::'#######::'########:::::'###::::'##:::::::::::::'##::::'###::::'########::'####:
:::::::::'##... ##:: ##:::::::'##.... ##: ##.... ##:::'## ##::: ##::::::::::::'##::::'## ##::: ##.... ##:. ##::
::::::::: ##:::..::: ##::::::: ##:::: ##: ##:::: ##::'##:. ##:: ##:::::::::::'##::::'##:. ##:: ##:::: ##:: ##::
'#######: ##::'####: ##::::::: ##:::: ##: ########::'##:::. ##: ##::::::::::'##::::'##:::. ##: ########::: ##::
........: ##::: ##:: ##::::::: ##:::: ##: ##.... ##: #########: ##:::::::::'##::::: #########: ##.....:::: ##::
::::::::: ##::: ##:: ##::::::: ##:::: ##: ##:::: ##: ##.... ##: ##::::::::'##:::::: ##.... ##: ##::::::::: ##::
:::::::::. ######::: ########:. #######:: ########:: ##:::: ##: ########:'##::::::: ##:::: ##: ##::::::::'####:
::::::::::......::::........:::.......:::........:::..:::::..::........::..::::::::..:::::..::..:::::::::....::
"""


class TokenModifierBlock:
    @staticmethod
    def process(env: ProcessEnvironment) -> None:
        """
        Process modifier block
        -- global:
        -- api:
        """
        blockTokenInfoStack = []
        for sourceCursor, sourceLine in enumerate(env.sourceLines):
            # if blockTokenInfoStack is not empty and..
            # current indent level is less than or equal to the last blockTokenInfoStack indent level
            # pop stack until the indent level is less than current indent level
            while blockTokenInfoStack:
                blockTokenInfo = blockTokenInfoStack[-1]
                match = re.match(r'^(?P<indent> *)', sourceLine['line'])
                indentLevel = len(match.group('indent')) // 4
                if indentLevel <= blockTokenInfo['indentLevel']:
                    blockTokenInfoStack.pop()
                else:
                    break

            # when match global or api block
            # add token info to stack
            match = re.match(
                r'^(?P<indent> *)(?P<modifier>api|global)\s*:\s*$', sourceLine['line'])
            if match:
                blockTokenInfo = {
                    'indentLevel': len(match.group('indent')) // 4,
                    'cursor': len(env.nextLines),
                    'modifier': match.group('modifier'),
                }
                blockTokenInfoStack.append(blockTokenInfo)
                continue

            # anything else
            # add the modifier tag to the line if blockTokenInfoStack is not empty
            if blockTokenInfoStack:
                sourceLine['tags']['modifier'] = blockTokenInfoStack[-1]['modifier']
                # make 1 level less indent
                match = re.match(r'^(?P<indent> *)', sourceLine['line'])
                indentLevel = len(match.group('indent')) // 4
                if indentLevel > 1:
                    env.nextLines.append(
                        {'tags': sourceLine['tags'], 'cursor': sourceLine['cursor'], 'line': f'{sourceLine["line"][4:]}'})
                else:
                    env.nextLines.append(sourceLine)
                continue

            # add the line to nextLines
            env.nextLines.append(sourceLine)


"""
:::'###::::'##:::::::'####::::'###:::::'######::
::'## ##::: ##:::::::. ##::::'## ##:::'##... ##:
:'##:. ##:: ##:::::::: ##:::'##:. ##:: ##:::..::
'##:::. ##: ##:::::::: ##::'##:::. ##:. ######::
 #########: ##:::::::: ##:: #########::..... ##:
 ##.... ##: ##:::::::: ##:: ##.... ##:'##::: ##:
 ##:::: ##: ########:'####: ##:::: ##:. ######::
..:::::..::........::....::..:::::..:::......:::
"""


class TokenTypeAlias:
    # static dictionary to hold type aliases
    typeAliases = {
        'int': 'integer',
        'str': 'string',
        'bool': 'boolean',
        'void': 'nothing',
        'table': 'hashtable',
    }

    @staticmethod
    def process(env: ProcessEnvironment) -> None:
        # expression: alias <typeName> extends <originalType>
        for sourceCursor, sourceLine in enumerate(env.sourceLines):
            match = re.match(
                r'^(?P<indent> *)alias\s+(?P<typeName>[a-zA-Z0-9_-][a-zA-Z0-9_.-]*)\s+extends\s+(?P<originalType>[a-zA-Z0-9_-][a-zA-Z0-9_.-]*)\s*$', sourceLine['line'])
            if match:
                typeName = match.group('typeName')
                originalType = match.group('originalType')

                # aliases are saved in the memory for later resolution
                TokenTypeAlias.typeAliases[typeName] = originalType
                # alias definition does not generate any code
                continue

            # anything else
            env.nextLines.append(sourceLine)

    @staticmethod
    def getActualType(typeName: str) -> str:
        return TokenTypeAlias.typeAliases.get(typeName, typeName)


"""
:::::::::'########:'##:::'##:'########::'########:
:::::::::... ##..::. ##:'##:: ##.... ##: ##.....::
:::::::::::: ##:::::. ####::: ##:::: ##: ##:::::::
'#######:::: ##::::::. ##:::: ########:: ######:::
........:::: ##::::::: ##:::: ##.....::: ##...::::
:::::::::::: ##::::::: ##:::: ##:::::::: ##:::::::
:::::::::::: ##::::::: ##:::: ##:::::::: ########:
::::::::::::..::::::::..:::::..:::::::::........::
"""


class TokenType:
    @staticmethod
    def process(env: ProcessEnvironment) -> None:
        for sourceCursor, sourceLine in enumerate(env.sourceLines):
            # type statement
            match = re.match(
                r'^(?P<indent> *)(?:(?P<modifier>api|global)\s+)?type\s+(?P<typeName>[a-zA-Z0-9_-][a-zA-Z0-9_.-]*)(\s+(?P<hasextends>extends)\s+(?P<extends>[a-zA-Z0-9_-][a-zA-Z0-9_.-]*))?\s*$', sourceLine['line'])
            if match:
                typeIndent = match.group('indent')

                typeModifier = sourceLine['tags'].get('modifier', None)
                if typeModifier is None:
                    typeModifier = match.group('modifier')
                elif match.group('modifier') is not None:
                    raise DslSyntaxError(
                        env.sourcePath, sourceLine['cursor'], sourceLine['line'], f'Modifier tag already exists: "{typeModifier}" on parent block and "{match.group("modifier")}" on itself')
                if typeModifier == 'api':
                    typeModifier = 'public '
                elif typeModifier == 'global':
                    typeModifier = ''
                else:
                    typeModifier = 'private '

                typeName = match.group('typeName')
                typeHasExtends = match.group('hasextends')
                typeExtends = match.group('extends')

                # if typeHasExtends but typeExtends is None, raise syntax error
                if typeHasExtends and typeExtends is None:
                    raise DslSyntaxError(
                        env.sourcePath, sourceLine['cursor'], sourceLine['line'], f'Extend type is not specified')

                if typeHasExtends is None:
                    typeExtends = ' extends array'
                elif typeExtends == 'handle':
                    typeExtends = ''
                else:
                    typeExtends = ' extends array'

                env.nextLines.append(
                    {'tags': {}, 'cursor': sourceLine['cursor'], 'line': f'{typeIndent}{typeModifier}struct {typeName}{typeExtends}'})
                env.nextLines.append(
                    {'tags': {}, 'cursor': sourceLine['cursor'], 'line': f'{typeIndent}endstruct'})
                continue

            # anything else
            env.nextLines.append(sourceLine)


"""
:::::::::'####:'##::: ##:'####:'########:
:::::::::. ##:: ###:: ##:. ##::... ##..::
:::::::::: ##:: ####: ##:: ##::::: ##::::
'#######:: ##:: ## ## ##:: ##::::: ##::::
........:: ##:: ##. ####:: ##::::: ##::::
:::::::::: ##:: ##:. ###:: ##::::: ##::::
:::::::::'####: ##::. ##:'####:::: ##::::
:::::::::....::..::::..::....:::::..:::::
"""


class TokenInitFunc:
    @staticmethod
    def process(env: ProcessEnvironment) -> None:
        initFunctionBlock = False
        initFunctionIndentLevel = 0
        for sourceLine in env.sourceLines:
            # check exiting init block
            if initFunctionBlock:
                match = re.match(r'^(?P<indent> *)',
                                 sourceLine['line'])
                if match:
                    indentLevel = len(match.group('indent')) // 4
                    if indentLevel <= initFunctionIndentLevel:
                        # exiting init block
                        env.nextLines.append(
                            {'tags': {}, 'cursor': sourceLine['cursor'], 'line': f'{"    "*initFunctionIndentLevel}endfunction'})
                        initFunctionBlock = False
                    else:
                        # inside init block
                        sourceLine['tags']['function'] = True
                        env.nextLines.append(sourceLine)
                        continue

            # init: block
            match = re.match(
                r'^(?P<indent> *)init\s*:\s*$', sourceLine['line'])
            if match:
                initFunctionBlock = True
                indent = match.group('indent')
                initFunctionIndentLevel = len(indent) // 4
                functionName = f'VJPI{generateUUID()}'
                env.nextLines.append(
                    {'tags': {'init': True}, 'cursor': sourceLine['cursor'], 'line': f'{indent}private function {functionName} takes nothing returns nothing'})
                continue

            # anything else
            env.nextLines.append(sourceLine)

        if initFunctionBlock:
            # if the init block is not closed, close it
            env.nextLines.append(
                {'tags': {}, 'cursor': sourceLine['cursor'], 'line': f'{"    "*initFunctionIndentLevel}endfunction'})
            initFunctionBlock = False


"""
:::::::::'########::'########::'#######::'##::::'##:'####:'########::'########:
::::::::: ##.... ##: ##.....::'##.... ##: ##:::: ##:. ##:: ##.... ##: ##.....::
::::::::: ##:::: ##: ##::::::: ##:::: ##: ##:::: ##:: ##:: ##:::: ##: ##:::::::
'#######: ########:: ######::: ##:::: ##: ##:::: ##:: ##:: ########:: ######:::
........: ##.. ##::: ##...:::: ##:'## ##: ##:::: ##:: ##:: ##.. ##::: ##...::::
::::::::: ##::. ##:: ##::::::: ##:.. ##:: ##:::: ##:: ##:: ##::. ##:: ##:::::::
::::::::: ##:::. ##: ########:: ##### ##:. #######::'####: ##:::. ##: ########:
:::::::::..:::::..::........:::.....:..:::.......:::....::..:::::..::........::
"""


class TokenRequire:
    @staticmethod
    def process(env: ProcessEnvironment) -> None:
        for sourceLine in env.sourceLines:
            # require statement
            # -- require <name>
            # -- require optional <name>
            match = re.match(
                r'^(?P<indent> *)uses(?P<optional>\s+optional)?\s+(?P<name>[a-zA-Z0-9_-][a-zA-Z0-9_.-]*)\s*$', sourceLine['line'])

            if match:
                # apply require tag or require optional tag
                if match.group('optional'):
                    sourceLine['tags']['require'] = f'optional {match.group("name")}'
                else:
                    sourceLine['tags']['require'] = f'{match.group("name")}'
                # add require statement to the next line
                env.nextLines.append(sourceLine)
                continue

            # anything else
            env.nextLines.append(sourceLine)


"""
:::::::::'##:::::::'####:'########::'########:::::'###::::'########::'##:::'##:
::::::::: ##:::::::. ##:: ##.... ##: ##.... ##:::'## ##::: ##.... ##:. ##:'##::
::::::::: ##:::::::: ##:: ##:::: ##: ##:::: ##::'##:. ##:: ##:::: ##::. ####:::
'#######: ##:::::::: ##:: ########:: ########::'##:::. ##: ########::::. ##::::
........: ##:::::::: ##:: ##.... ##: ##.. ##::: #########: ##.. ##:::::: ##::::
::::::::: ##:::::::: ##:: ##:::: ##: ##::. ##:: ##.... ##: ##::. ##::::: ##::::
::::::::: ########:'####: ########:: ##:::. ##: ##:::: ##: ##:::. ##:::: ##::::
:::::::::........::....::........:::..:::::..::..:::::..::..:::::..:::::..:::::
"""


class TokenLibrary:
    @staticmethod
    def process(env: ProcessEnvironment) -> None:
        libraryInfo = None
        inLibrary = False

        def finalizeLibraryBlock(libraryInfo):
            nonlocal inLibrary
            requireStatement = ''
            if libraryInfo['requires']:
                requireStatement = f' requires {', '.join(libraryInfo["requires"])}'

            if libraryInfo['inits']:
                # if libraryInfo['inits'] is not empty:
                env.nextLines.insert(
                    libraryInfo['cursor'], {'tags': {}, 'line': f'library {libraryInfo["name"]} initializer onInit{requireStatement}'})
                env.nextLines.append(
                    {'tags': {'library': True}, 'line': f'    private function onInit takes nothing returns nothing'})
                for initFuncName in libraryInfo['inits']:
                    env.nextLines.append(
                        {'tags': {'library': True, 'function': True}, 'line': f'        call {initFuncName}()'})
                env.nextLines.append(
                    {'tags': {'library': True}, 'line': '    endfunction'})
            else:
                env.nextLines.insert(
                    libraryInfo['cursor'], {'tags': {}, 'line': f'library {libraryInfo["name"]}{requireStatement}'})
            env.nextLines.append({'tags': {}, 'line': 'endlibrary'})
            inLibrary = False

        for sourceCursor, sourceLine in enumerate(env.sourceLines):
            # check library block end
            if libraryInfo is not None and re.match(r'^[^\s]+', sourceLine['line']):
                finalizeLibraryBlock(libraryInfo)
                libraryInfo = None

            # library statement
            match = re.match(
                r'^(?P<indent> *)(?P<librarytype>library|data|system)\s+(?P<libraryName>[a-zA-Z0-9_-][a-zA-Z0-9_.-]*)\s*:\s*$', sourceLine['line'])
            if match:
                libraryType = match.group('librarytype')
                libraryInfo = {
                    'indentLevel': len(match.group('indent')) // 4,
                    'cursor': len(env.nextLines),
                    'name': match.group('libraryName'),
                    'type': libraryType,
                    'inits': [],
                    'requires': [],
                }
                if libraryType == 'library':
                    env.libraries.append(libraryInfo['name'])
                elif libraryType == 'data':
                    env.datalibs.append(libraryInfo['name'])
                    libraryInfo['requires'].append('VJPLIBS')
                elif libraryType == 'system':
                    env.systems.append(libraryInfo['name'])
                    libraryInfo['requires'].append('VJPDATA')
                inLibrary = True
                continue

            # initializer support - 태그 기반 검사로 변경
            if sourceLine['tags'].get('init', False) and libraryInfo is not None:
                initFuncMatch = re.match(
                    r'^ *private function\s+([a-zA-Z0-9_-][a-zA-Z0-9_.-]*)\s+', sourceLine['line'])
                if initFuncMatch:
                    initFuncName = initFuncMatch.group(1)
                    libraryInfo['inits'].append(initFuncName)
                    sourceLine['tags']['library'] = True
                    env.nextLines.append(sourceLine)
                    continue

            # require support - 태그 기반 검사로 변경
            if sourceLine['tags'].get('require', False) and libraryInfo is not None:
                libraryInfo['requires'].append(
                    sourceLine['tags']['require'])
                # actual require line is not needed in the library block
                continue

            # anything else
            if inLibrary:
                sourceLine['tags']['library'] = True
            env.nextLines.append(sourceLine)

        if libraryInfo is not None:
            # if the library block is not closed, close it
            finalizeLibraryBlock(libraryInfo)


"""
::::::::::'######:::'######:::'#######::'########::'########:
:::::::::'##... ##:'##... ##:'##.... ##: ##.... ##: ##.....::
::::::::: ##:::..:: ##:::..:: ##:::: ##: ##:::: ##: ##:::::::
'#######:. ######:: ##::::::: ##:::: ##: ########:: ######:::
........::..... ##: ##::::::: ##:::: ##: ##.....::: ##...::::
:::::::::'##::: ##: ##::: ##: ##:::: ##: ##:::::::: ##:::::::
:::::::::. ######::. ######::. #######:: ##:::::::: ########:
::::::::::......::::......::::.......:::..:::::::::........::
"""


class TokenScope:
    @staticmethod
    def process(env: ProcessEnvironment) -> None:
        contentInfo = None
        inContent = False

        def finalizeContentBlock(contentInfo):
            nonlocal inContent
            if contentInfo['inits']:
                # if contentInfo['inits'] is not empty:
                env.nextLines.insert(
                    contentInfo['cursor'], {'tags': {}, 'line': f'scope {contentInfo["name"]} initializer onInit'})
                env.nextLines.append(
                    {'tags': {'content': True}, 'line': f'    private function onInit takes nothing returns nothing'})
                for initFuncName in contentInfo['inits']:
                    env.nextLines.append(
                        {'tags': {'content': True, 'function': True}, 'line': f'        call {initFuncName}()'})
                env.nextLines.append(
                    {'tags': {'content': True}, 'line': '    endfunction'})
            else:
                env.nextLines.insert(
                    contentInfo['cursor'], {'tags': {}, 'line': f'scope {contentInfo["name"]}'})
            env.nextLines.append({'tags': {}, 'line': 'endscope'})
            inContent = False

        for sourceCursor, sourceLine in enumerate(env.sourceLines):
            # check content block end
            if contentInfo is not None and re.match(r'^[^\s]+', sourceLine['line']):
                finalizeContentBlock(contentInfo)
                contentInfo = None

            # content statement
            match = re.match(
                r'^(?P<indent> *)content(?:\s+(?P<contentName>[a-zA-Z0-9_-][a-zA-Z0-9_.-]*))?\s*:\s*$', sourceLine['line'])
            if match:
                contentName = match.group('contentName')
                if contentName is None:
                    contentName = f'VJPS{generateUUID()}'
                contentInfo = {
                    'indentLevel': len(match.group('indent')) // 4,
                    'cursor': len(env.nextLines),
                    'name': contentName,
                    'inits': [],
                }
                inContent = True
                continue

            # initializer support - 태그 기반 검사로 변경
            if sourceLine['tags'].get('init', False) and contentInfo is not None:
                initFuncMatch = re.match(
                    r'^ *private function\s+([a-zA-Z0-9_-][a-zA-Z0-9_.-]*)\s+', sourceLine['line'])
                if initFuncMatch:
                    initFuncName = initFuncMatch.group(1)
                    contentInfo['inits'].append(initFuncName)
                    sourceLine['tags']['content'] = True
                    env.nextLines.append(sourceLine)
                    continue

            # anything else
            if inContent:
                sourceLine['tags']['content'] = True
            env.nextLines.append(sourceLine)

        if contentInfo is not None:
            # if the content block is not closed, close it
            finalizeContentBlock(contentInfo)


"""
:::::::::'##::: ##::::'###::::'########:'####:'##::::'##:'########:
::::::::: ###:: ##:::'## ##:::... ##..::. ##:: ##:::: ##: ##.....::
::::::::: ####: ##::'##:. ##::::: ##::::: ##:: ##:::: ##: ##:::::::
'#######: ## ## ##:'##:::. ##:::: ##::::: ##:: ##:::: ##: ######:::
........: ##. ####: #########:::: ##::::: ##::. ##:: ##:: ##...::::
::::::::: ##:. ###: ##.... ##:::: ##::::: ##:::. ## ##::: ##:::::::
::::::::: ##::. ##: ##:::: ##:::: ##::::'####:::. ###:::: ########:
:::::::::..::::..::..:::::..:::::..:::::....:::::...:::::........::
"""


class TokenNative:
    @staticmethod
    def process(env: ProcessEnvironment) -> None:
        for sourceLine in env.sourceLines:
            # native statement
            match = re.match(
                r'^(?P<indent> *)native\s+(?P<name>[a-zA-Z][a-zA-Z0-9_]*)\s*\((?P<takes>[^)]*)\)(?:\s*->\s*(?P<returns>\w+))?\s*$', sourceLine['line'])
            if match:
                nativeIndent = match.group('indent')
                nativeTakes = match.group('takes')
                if not nativeTakes:
                    nativeTakes = 'nothing'
                nativeReturns = match.group('returns')
                if not nativeReturns:
                    nativeReturns = 'nothing'

                # resolve takes aliases
                takes_str = nativeTakes.strip()
                if takes_str.lower() != 'nothing':
                    parts = [p.strip() for p in takes_str.split(',')]
                    resolved_parts = []
                    for p in parts:
                        pm = re.match(
                            r'^(?P<type>[a-zA-Z][a-zA-Z0-9_.-]*)\s+(?P<name>[a-zA-Z][a-zA-Z0-9_]*)$', p)
                        if pm:
                            t = TokenTypeAlias.getActualType(pm.group('type'))
                            resolved_parts.append(f'{t} {pm.group("name")}')
                        else:
                            resolved_parts.append(p)
                    nativeTakes = ', '.join(resolved_parts)
                else:
                    nativeTakes = 'nothing'

                # resolve return alias
                nativeReturns = TokenTypeAlias.getActualType(nativeReturns)

                env.nextLines.append(
                    {'tags': {'native': True}, 'line': f'{nativeIndent}native {match.group("name")} takes {nativeTakes} returns {nativeReturns}'})
                continue

            # anything else
            env.nextLines.append(sourceLine)


"""
:::::::::'########:'##::::'##:'##::: ##::'######::'########:'####::'#######::'##::: ##:
::::::::: ##.....:: ##:::: ##: ###:: ##:'##... ##:... ##..::. ##::'##.... ##: ###:: ##:
::::::::: ##::::::: ##:::: ##: ####: ##: ##:::..::::: ##::::: ##:: ##:::: ##: ####: ##:
'#######: ######::: ##:::: ##: ## ## ##: ##:::::::::: ##::::: ##:: ##:::: ##: ## ## ##:
........: ##...:::: ##:::: ##: ##. ####: ##:::::::::: ##::::: ##:: ##:::: ##: ##. ####:
::::::::: ##::::::: ##:::: ##: ##:. ###: ##::: ##:::: ##::::: ##:: ##:::: ##: ##:. ###:
::::::::: ##:::::::. #######:: ##::. ##:. ######::::: ##::::'####:. #######:: ##::. ##:
:::::::::..:::::::::.......:::..::::..:::......::::::..:::::....:::.......:::..::::..::
"""


class TokenFunction:
    @staticmethod
    def process(env: ProcessEnvironment) -> None:
        functionInfo = None

        for sourceCursor, sourceLine in enumerate(env.sourceLines):
            # check function block end
            if functionInfo is not None:
                match = re.match(r'^(?P<indent> *)',
                                 sourceLine['line'])
                if match:
                    indentLevel = len(match.group('indent')) // 4
                    if indentLevel <= functionInfo['indentLevel']:
                        # exiting function block
                        env.nextLines.append(
                            {'tags': {}, 'line': f'{"    "*functionInfo["indentLevel"]}endfunction'})
                        functionInfo = None
                    else:
                        # inside function block
                        tags = {
                            'function': True,
                            **sourceLine['tags']
                        }
                        env.nextLines.append(
                            {'tags': tags, 'cursor': sourceLine['cursor'], 'line': sourceLine['line']})
                        continue

            # function statement
            match = re.match(
                r'^(?P<indent> *)(?:(?P<modifier>api|global)\s+)?(?P<name>[a-zA-Z][a-zA-Z0-9_\.]*)\s*\((?P<takes>[^)]*)\)(?:\s*->\s*(?P<returns>\w+))?\s*:\s*$', sourceLine['line'])
            if match:
                # if function name contains two or more continuous underscore, raise syntax error
                functionName = match.group('name')
                if re.search(r'_{2,}', functionName):
                    raise DslSyntaxError(
                        env.sourcePath, sourceLine['cursor'], sourceLine['line'], f'Function name "{match.group("name")}" cannot contain two or more continuous underscore')

                functionIndent = match.group('indent')
                functionModifier = sourceLine['tags'].get('modifier', None)
                if functionModifier is None:
                    functionModifier = match.group('modifier')
                elif match.group('modifier') is not None:
                    raise DslSyntaxError(
                        env.sourcePath, sourceLine['cursor'], sourceLine['line'], f'Modifier tag already exists: "{functionModifier}" on parent block and "{match.group("modifier")}" on itself')
                if functionModifier == 'api':
                    functionModifier = 'public '
                elif functionModifier == 'global':
                    functionModifier = ''
                else:
                    functionModifier = 'private '

                functionTakes = match.group('takes')
                if not functionTakes:
                    functionTakes = 'nothing'
                functionReturns = match.group('returns')
                if not functionReturns:
                    functionReturns = 'nothing'

                # take type alias resolution
                functionTakesParts = []
                takes_str = functionTakes.strip()
                if takes_str.lower() != 'nothing':
                    params = [p.strip() for p in takes_str.split(',')]
                    for p in params:
                        pm = re.match(
                            r'^(?P<type>[a-zA-Z][a-zA-Z0-9_.-]*)\s+(?P<name>[a-zA-Z][a-zA-Z0-9_\.]*)$', p)
                        if pm:
                            resolved_type = TokenTypeAlias.getActualType(
                                pm.group('type'))
                            functionTakesParts.append(
                                f'{resolved_type} {pm.group("name")}')
                        elif p:  # fallback: keep as-is
                            functionTakesParts.append(p)
                    functionTakes = ', '.join(
                        functionTakesParts) if functionTakesParts else 'nothing'
                else:
                    functionTakes = 'nothing'

                # return type alias resolution
                functionReturns = TokenTypeAlias.getActualType(functionReturns)

                functionInfo = {
                    'cursor': sourceCursor,
                    'indentLevel': len(functionIndent) // 4,
                    'modifier': match.group('modifier'),
                    'name': functionName,
                    'takes': functionTakes,
                    'returns': functionReturns,
                }
                env.nextLines.append(
                    {'tags': sourceLine['tags'], 'line': f'{functionIndent}{functionModifier}function {functionInfo["name"]} takes {functionInfo["takes"]} returns {functionInfo["returns"]}'})
                continue

            # anything else
            env.nextLines.append(sourceLine)


"""
:::::::::'##::::'##::::'###::::'########::'####::::'###::::'########::'##:::::::'########:
::::::::: ##:::: ##:::'## ##::: ##.... ##:. ##::::'## ##::: ##.... ##: ##::::::: ##.....::
::::::::: ##:::: ##::'##:. ##:: ##:::: ##:: ##:::'##:. ##:: ##:::: ##: ##::::::: ##:::::::
'#######: ##:::: ##:'##:::. ##: ########::: ##::'##:::. ##: ########:: ##::::::: ######:::
........:. ##:: ##:: #########: ##.. ##:::: ##:: #########: ##.... ##: ##::::::: ##...::::
::::::::::. ## ##::: ##.... ##: ##::. ##::: ##:: ##.... ##: ##:::: ##: ##::::::: ##:::::::
:::::::::::. ###:::: ##:::: ##: ##:::. ##:'####: ##:::: ##: ########:: ########: ########:
::::::::::::...:::::..:::::..::..:::::..::....::..:::::..::........:::........::........::
"""


class TokenVariable:
    @staticmethod
    def process(env: ProcessEnvironment) -> None:
        globalBlock = False
        globalTags = None
        globalIndentLevel = 0
        for sourceCursor, sourceLine in enumerate(env.sourceLines):
            # variable statement
            match = re.match(
                r'^(?P<indent> *)(?:(?P<modifier>api|global)\s+)?(?P<type>[a-zA-Z][a-zA-Z0-9\.]*)\s+(?P<name>[a-zA-Z][a-zA-Z0-9_\.]*)(?:\s*(?P<let>=|~)\s*(?P<value>.*?))?\s*$', sourceLine['line'])
            if match and not re.match(r'\b(library|data|system|scope|content|return|if|elseif|else|loop|while|until|exitwhen)\b', match.group('type')):
                variableIndent = match.group('indent')
                variableModifier = sourceLine['tags'].get('modifier', None)
                if variableModifier is None:
                    variableModifier = match.group('modifier')
                elif match.group('modifier') is not None:
                    raise DslSyntaxError(
                        env.sourcePath, sourceLine['cursor'], sourceLine['line'], f'Modifier tag already exists: "{variableModifier}" on parent block and "{match.group("modifier")}" on itself')
                if variableModifier == 'api':
                    variableModifier = 'public '
                elif variableModifier == 'global':
                    variableModifier = ''
                else:
                    variableModifier = 'private '
                variableLet = match.group('let') == '='
                variableType = match.group('type')
                # resolve type aliases
                variableType = TokenTypeAlias.getActualType(variableType)
                variableName = match.group('name')
                variableValue = match.group('value')

                # Check if this is a local variable (in function)
                isLocal = sourceLine['tags'].get('function', False)

                # Perform different actions based on local/global variable
                if isLocal:
                    variableResult = f'{variableIndent}'
                    # Local variables don't need access modifiers but local
                    variableResult += 'local '
                    if not variableLet:
                        variableResult += 'constant '
                else:
                    variableResult = f'{variableIndent}    '
                    # Global variables need global blocks
                    if not globalBlock:
                        match = re.match(
                            r'^(?P<indent> *)', sourceLine['line'])
                        if match:
                            indentLevel = len(
                                match.group('indent')) // 4
                            globalIndentLevel = indentLevel
                            globalTags = sourceLine['tags']
                            env.nextLines.append(
                                {'tags': globalTags, 'line': f'{"    "*globalIndentLevel}globals'})
                            globalBlock = True

                    variableResult += variableModifier
                    if not variableLet:
                        variableResult += 'constant '

                if not variableValue:
                    variableResult += f'{variableType} {variableName}'
                elif re.match(r'^\[[^\]]*\]$', variableValue):
                    variableResult += f'{variableType} array {variableName}'
                elif re.match(r'^\{[^\}]*\}', variableValue):
                    variableResult += f'{variableType} {variableName} = InitHashtable()'
                elif variableType == 'integer' and variableValue == 'null':
                    variableResult += f'{variableType} {variableName} = 0'
                else:
                    variableResult += f'{variableType} {variableName} = {variableValue}'

                env.nextLines.append(
                    {'tags': sourceLine['tags'], 'line': variableResult})
                continue

            # anything else
            if globalBlock:
                match = re.match(r'^(?P<indent> *)',
                                 sourceLine['line'])
                if match:
                    indentLevel = len(match.group('indent')) // 4
                    if indentLevel <= globalIndentLevel:
                        # exiting global block
                        env.nextLines.append(
                            {'tags': globalTags, 'line': f'{"    "*globalIndentLevel}endglobals'})
                        globalBlock = False
                    else:
                        # inside global block
                        sourceLine['tags']['global'] = True
                        env.nextLines.append(sourceLine)
                        continue

            env.nextLines.append(sourceLine)

        if globalBlock:
            # if the global block is not closed, close it
            env.nextLines.append(
                {'tags': globalTags, 'line': f'{"    "*globalIndentLevel}endglobals'})
            globalBlock = False


"""
:::::::::'##::::::::'#######:::'#######::'########:::'######::
::::::::: ##:::::::'##.... ##:'##.... ##: ##.... ##:'##... ##:
::::::::: ##::::::: ##:::: ##: ##:::: ##: ##:::: ##: ##:::..::
'#######: ##::::::: ##:::: ##: ##:::: ##: ########::. ######::
........: ##::::::: ##:::: ##: ##:::: ##: ##.....::::..... ##:
::::::::: ##::::::: ##:::: ##: ##:::: ##: ##::::::::'##::: ##:
::::::::: ########:. #######::. #######:: ##::::::::. ######::
:::::::::........:::.......::::.......:::..::::::::::......:::
"""


class TokenLoops:
    @staticmethod
    def process(env: ProcessEnvironment) -> None:
        loopBlockStack = []
        for sourceCursor, sourceLine in enumerate(env.sourceLines):
            # match loop: block
            match = re.match(
                r'^(?P<indent> *)loop\s*:\s*$', sourceLine['line'])
            if match:
                loopIndent = match.group('indent')
                loopIndentLevel = len(loopIndent) // 4
                loopBlockStack.append({
                    'cursor': sourceCursor,
                    'indentLevel': loopIndentLevel,
                })
                env.nextLines.append(
                    {'tags': sourceLine['tags'], 'line': f'{loopIndent}loop'})
                continue

            # match while condition_expression: block
            match = re.match(
                r'^(?P<indent> *)while\s+(?P<condition>.*?):\s*$', sourceLine['line'])
            if match:
                loopIndent = match.group('indent')
                loopIndentLevel = len(loopIndent) // 4
                loopBlockStack.append({
                    'cursor': sourceCursor,
                    'indentLevel': loopIndentLevel,
                })
                conditionExpression = match.group('condition')
                env.nextLines.append(
                    {'tags': sourceLine['tags'], 'line': f'{loopIndent}loop'})
                env.nextLines.append(
                    {'tags': sourceLine['tags'], 'line': f'{loopIndent}    exitwhen not ({conditionExpression})'})
                continue

            # match until condition_expression: block
            match = re.match(
                r'^(?P<indent> *)until\s+(?P<condition>.*?):\s*$', sourceLine['line'])
            if match:
                loopIndent = match.group('indent')
                loopIndentLevel = len(loopIndent) // 4
                loopBlockStack.append({
                    'cursor': sourceCursor,
                    'indentLevel': loopIndentLevel,
                })
                conditionExpression = match.group('condition')
                env.nextLines.append(
                    {'tags': sourceLine['tags'], 'line': f'{loopIndent}loop'})
                env.nextLines.append(
                    {'tags': sourceLine['tags'], 'line': f'{loopIndent}    exitwhen {conditionExpression}'})
                continue

            # match repeat statement
            # match = re.match(
            #     r'^(?P<indent> *)repeat\s+(?P<count>\S+)(?:\s+with\s+(?P<with>\S+))?(?:\s+from\s+(?P<from>\S+))?\s*:\s*$', sourceLine['line'])
            # if match:
            #     loopIndent = match.group('indent')
            #     loopIndentLevel = len(loopIndent) // 4
            #     loopBlockStack.append({
            #         'cursor': sourceCursor,
            #         'indentLevel': loopIndentLevel,
            #     })
            #     count = match.group('count')
            #     withValue = match.group('with')
            #     if not withValue:
            #         withValue = f'vjsr{generateUUID()}'
            #     if not fromValue:
            #         fromValue = '0'

            #     # append variable declaration
            #     if match.group('with'):
            #         env.nextLines.append(
            #             {'tags': sourceLine['tags'], 'line': f'{loopIndent}set {withValue} = {fromValue}'})
            #         env.nextLines.append(
            #             {'tags': sourceLine['tags'], 'line': f'{loopIndent}local integer vjsr_{withValue}_{generateUUID()} = {fromValue}'})
            #     else:
            #         env.nextLines.append(
            #             {'tags': sourceLine['tags'], 'line': f'{loopIndent}local integer {withValue} = {fromValue}'})
            #     # append loop block
            #     env.nextLines.append(
            #         {'tags': sourceLine['tags'], 'line': f'{loopIndent}loop'})

            # anything else but was in loop block
            if len(loopBlockStack) > 0:
                # pop loop block until the indent level is less than the current line
                while len(loopBlockStack) > 0:
                    loopBlock = loopBlockStack[-1]
                    match = re.match(
                        r'^(?P<indent> *)', sourceLine['line'])
                    if match:
                        indentLevel = len(match.group('indent')) // 4
                        if indentLevel <= loopBlock['indentLevel']:
                            # exiting loop block
                            env.nextLines.append(
                                {'tags': {}, 'line': f'{"    "*loopBlock["indentLevel"]}endloop'})
                            loopBlockStack.pop()
                            continue
                        else:
                            break

            # match break statement
            match = re.match(
                r'^(?P<indent> *)break\s*$', sourceLine['line'])
            if match:
                # replace with 'exitwhen true'
                env.nextLines.append(
                    {'tags': sourceLine['tags'], 'line': f'{match.group("indent")}exitwhen true'})
                continue

            # anything else
            env.nextLines.append(sourceLine)

        while len(loopBlockStack) > 0:
            # if the loop block is not closed, close it
            loopBlock = loopBlockStack.pop()
            env.nextLines.append(
                {'tags': {}, 'line': f'{"    "*loopBlock["indentLevel"]}endloop'})
            loopBlockStack = []


"""
:::::::::'####:'########:
:::::::::. ##:: ##.....::
:::::::::: ##:: ##:::::::
'#######:: ##:: ######:::
........:: ##:: ##...::::
:::::::::: ##:: ##:::::::
:::::::::'####: ##:::::::
:::::::::....::..::::::::
"""


class TokenIfBlock:
    @staticmethod
    def process(env: ProcessEnvironment) -> None:
        ifBlockStack = []

        def closeIfBlocks(ifBlockStack, env, indentLevel):
            while len(ifBlockStack) > 0:
                ifBlock = ifBlockStack[-1]
                if ifBlock['indentLevel'] < indentLevel:
                    break
                # exiting if block
                ifBlockStack.pop()
                env.nextLines.append(
                    {'tags': {}, 'line': f'{"    "*ifBlock["indentLevel"]}endif'})

        for sourceCursor, sourceLine in enumerate(env.sourceLines):
            # match if condition_expression: block
            match = re.match(
                r'^(?P<indent> *)if\s+(?P<condition>.*?):\s*$', sourceLine['line'])
            if match:
                ifIndent = match.group('indent')
                ifIndentLevel = len(ifIndent) // 4
                # close all if blocks that have higher or equal indent level
                closeIfBlocks(ifBlockStack, env, ifIndentLevel)
                ifBlockStack.append({
                    'cursor': sourceCursor,
                    'indentLevel': ifIndentLevel,
                    'tags': sourceLine['tags'],
                })
                conditionExpression = match.group('condition')
                env.nextLines.append(
                    {'tags': sourceLine['tags'], 'line': f'{ifIndent}if {conditionExpression} then'})
                continue

            # match elseif condition_expression: block
            match = re.match(
                r'^(?P<indent> *)elseif\s+(?P<condition>.*?):\s*$', sourceLine['line'])
            if match:
                # close all if blocks that have higher indent level
                closeIfBlocks(ifBlockStack, env, len(
                    match.group('indent')) // 4 + 1)
                conditionExpression = match.group('condition')
                env.nextLines.append(
                    {'tags': sourceLine['tags'], 'line': f'{"    "*ifBlockStack[-1]["indentLevel"]}elseif {conditionExpression} then'})
                continue

            # match else: block
            match = re.match(
                r'^(?P<indent> *)else\s*:\s*$', sourceLine['line'])
            if match:
                # close all if blocks that have higher indent level
                closeIfBlocks(ifBlockStack, env, len(
                    match.group('indent')) // 4 + 1)
                env.nextLines.append(
                    {'tags': sourceLine['tags'], 'line': f'{"    "*ifBlockStack[-1]["indentLevel"]}else'})
                continue

            # pop if block until the indent level is less than the current line
            match = re.match(
                r'^(?P<indent> *)', sourceLine['line'])
            if match:
                indentLevel = len(match.group('indent')) // 4
                # close all if blocks that have higher indent level
                closeIfBlocks(ifBlockStack, env, indentLevel)

            # anything else
            env.nextLines.append(sourceLine)

        while len(ifBlockStack) > 0:
            # if the loop block is not closed, close it
            ifBlock = ifBlockStack.pop()
            env.nextLines.append(
                {'tags': {}, 'line': f'{"    "*ifBlock["indentLevel"]}endif'})
            ifBlockStack


"""
::::::::::'######:::::'###::::'##:::::::'##:::::::::::::'##::'######::'########:'########:
:::::::::'##... ##:::'## ##::: ##::::::: ##::::::::::::'##::'##... ##: ##.....::... ##..::
::::::::: ##:::..:::'##:. ##:: ##::::::: ##:::::::::::'##::: ##:::..:: ##:::::::::: ##::::
'#######: ##:::::::'##:::. ##: ##::::::: ##::::::::::'##::::. ######:: ######:::::: ##::::
........: ##::::::: #########: ##::::::: ##:::::::::'##::::::..... ##: ##...::::::: ##::::
::::::::: ##::: ##: ##.... ##: ##::::::: ##::::::::'##::::::'##::: ##: ##:::::::::: ##::::
:::::::::. ######:: ##:::: ##: ########: ########:'##:::::::. ######:: ########:::: ##::::
::::::::::......:::..:::::..::........::........::..:::::::::......:::........:::::..:::::
"""


class TokenCodePrefix:
    @staticmethod
    def process(env: ProcessEnvironment) -> None:
        """
        within lines that have 'function' tag, we need to ensure that each line starts with proper prefix
        automatically add 'call' to the function call statement
        and automatically add 'set' to the variable assignment statement
        """
        for sourceLine in env.sourceLines:
            # check if the line is a function call or variable assignment
            if sourceLine['tags'].get('function', False):
                # function call
                match = re.match(
                    r'^(?P<indent> *)(?P<name>[a-zA-Z][a-zA-Z0-9_.\[\]]*\s*\(.*?\))\s*$', sourceLine['line'])
                if match:
                    functionIndent = match.group('indent')
                    functionName = match.group('name')
                    env.nextLines.append(
                        {'tags': sourceLine['tags'], 'line': f'{functionIndent}call {functionName}'})
                    continue

                # variable assignment
                match = re.match(
                    r'^(?P<indent> *)(?P<name>[a-zA-Z][a-zA-Z0-9_.\[\]:]*)\s*(?P<operator>=|\+\+|\-\-|\*\*|!!|//|\+=|\-=|\*=|/=)\s*(?P<value>.*)$', sourceLine['line'])
                if match:
                    variableIndent = match.group('indent')
                    variableName = match.group('name')
                    variableValue = match.group('value')
                    variableOperator = match.group('operator')

                    if variableOperator == '=':
                        env.nextLines.append(
                            {'tags': sourceLine['tags'], 'line': f'{variableIndent}set {variableName} = {variableValue}'})
                    elif variableOperator == '++':
                        env.nextLines.append(
                            {'tags': sourceLine['tags'], 'line': f'{variableIndent}set {variableName} = {variableName} + 1'})
                    elif variableOperator == '--':
                        env.nextLines.append(
                            {'tags': sourceLine['tags'], 'line': f'{variableIndent}set {variableName} = {variableName} - 1'})
                    elif variableOperator == '**':
                        env.nextLines.append(
                            {'tags': sourceLine['tags'], 'line': f'{variableIndent}set {variableName} = {variableName} * 2'})
                    elif variableOperator == '//':
                        env.nextLines.append(
                            {'tags': sourceLine['tags'], 'line': f'{variableIndent}set {variableName} = {variableName} / 2'})
                    elif variableOperator == '!!':
                        env.nextLines.append(
                            {'tags': sourceLine['tags'], 'line': f'{variableIndent}set {variableName} = not {variableName}'})
                    elif variableOperator == '+=':
                        env.nextLines.append(
                            {'tags': sourceLine['tags'], 'line': f'{variableIndent}set {variableName} = {variableName} + {variableValue}'})
                    elif variableOperator == '-=':
                        env.nextLines.append(
                            {'tags': sourceLine['tags'], 'line': f'{variableIndent}set {variableName} = {variableName} - {variableValue}'})
                    elif variableOperator == '*=':
                        env.nextLines.append(
                            {'tags': sourceLine['tags'], 'line': f'{variableIndent}set {variableName} = {variableName} * {variableValue}'})
                    elif variableOperator == '/=':
                        env.nextLines.append(
                            {'tags': sourceLine['tags'], 'line': f'{variableIndent}set {variableName} = {variableName} / {variableValue}'})
                    else:
                        # unknown operator, just append the line as is
                        env.nextLines.append(sourceLine)
                    continue

            # anything else
            env.nextLines.append(sourceLine)


"""
:::::::::'##::::'##::'#######::'####::'######::'########:'####:'##::: ##::'######:::
::::::::: ##:::: ##:'##.... ##:. ##::'##... ##:... ##..::. ##:: ###:: ##:'##... ##::
::::::::: ##:::: ##: ##:::: ##:: ##:: ##:::..::::: ##::::: ##:: ####: ##: ##:::..:::
'#######: #########: ##:::: ##:: ##::. ######::::: ##::::: ##:: ## ## ##: ##::'####:
........: ##.... ##: ##:::: ##:: ##:::..... ##:::: ##::::: ##:: ##. ####: ##::: ##::
::::::::: ##:::: ##: ##:::: ##:: ##::'##::: ##:::: ##::::: ##:: ##:. ###: ##::: ##::
::::::::: ##:::: ##:. #######::'####:. ######::::: ##::::'####: ##::. ##:. ######:::
:::::::::..:::::..:::.......:::....:::......::::::..:::::....::..::::..:::......::::
"""


class TokenHoisting:
    @staticmethod
    def process(env: ProcessEnvironment) -> None:
        """
        In vJass, all local variables must be declared at the beginning of the function.
        This function will hoist all local variable declarations to the top of the function block.
        and leave assignments in the original place. (if possible)
        """
        hoistPositionStack = []

        for sourceCursor, sourceLine in enumerate(env.sourceLines):
            # check if we met a function statement
            match = re.match(
                r'^(?P<indent> *)(?:(?P<modifier>private|public)\s+)?function\s+(?P<name>[a-zA-Z][a-zA-Z0-9]*)', sourceLine['line'])
            if match:
                hoistPositionStack.append({
                    'cursor': len(env.nextLines),
                    'indentLevel': len(match.group('indent')) // 4,
                    'tags': sourceLine['tags'],
                })
                env.nextLines.append(sourceLine)
                continue

            # if hoistPositionStack is not empty, and we met lower or equal indent level, we need to pop the stack
            if len(hoistPositionStack) > 0:
                match = re.match(r'^(?P<indent> *)',
                                 sourceLine['line'])
                indentLevel = len(match.group('indent')) // 4
                while len(hoistPositionStack) > 0 and indentLevel <= hoistPositionStack[-1]['indentLevel']:
                    hoistPositionStack.pop()

            # check if we met a local variable declaration
            match = re.match(
                r'^(?P<indent> *)local\s+(?P<constant>constant\s+)?(?P<type>[a-zA-Z][a-zA-Z0-9]*)\s+(?:(?P<array>array)\s+)?(?P<name>[a-zA-Z][a-zA-Z0-9_]*)(?:\s*=\s*(?P<value>.*?))?\s*$', sourceLine['line'])
            if match:
                # check if we need hoist this variable
                # -- if hoistPositionStack is not empty and the cursor is right after the hoist position, we dont need to hoist this variable
                if len(hoistPositionStack) > 0 and len(env.nextLines) == hoistPositionStack[-1]['cursor'] + 1:
                    # update the hoist position to the next line
                    hoistPositionStack[-1]['cursor'] += 1
                    env.nextLines.append(sourceLine)
                    continue

                # -- if cursor is not right after the hoist position, we need to hoist this variable
                variableIndent = match.group('indent')
                variableConstant = match.group('constant')
                variableType = match.group('type')
                variableName = match.group('name')
                variableArray = match.group('array')
                variableValue = match.group('value')

                # insert hoisted variable declaration at the hoist position
                hoistCode = f'    {"    "*hoistPositionStack[-1]["indentLevel"]}local '
                if variableConstant:
                    hoistCode += 'constant '
                hoistCode += variableType
                if variableArray:
                    hoistCode += ' array'

                hoistCode += f' {variableName}'

                if variableConstant:
                    hoistCode += f' = {variableValue}'

                env.nextLines.insert(
                    hoistPositionStack[-1]['cursor'] + 1, {'tags': sourceLine['tags'], 'line': hoistCode})
                hoistPositionStack[-1]['cursor'] += 1

                # if the variable has an assignment, we need to add it to the next line
                if not variableConstant and variableValue:
                    env.nextLines.append(
                        {'tags': sourceLine['tags'], 'line': f'{variableIndent}set {variableName} = {variableValue}'})
                continue

            # anything else
            env.nextLines.append(sourceLine)


"""
:::::::::'########::'######::'########:'########::'####:'##::: ##::'######:::
::::::::: ##.....::'##... ##:... ##..:: ##.... ##:. ##:: ###:: ##:'##... ##::
::::::::: ##::::::: ##:::..::::: ##:::: ##:::: ##:: ##:: ####: ##: ##:::..:::
'#######: ######:::. ######::::: ##:::: ########::: ##:: ## ## ##: ##::'####:
........: ##...:::::..... ##:::: ##:::: ##.. ##:::: ##:: ##. ####: ##::: ##::
::::::::: ##:::::::'##::: ##:::: ##:::: ##::. ##::: ##:: ##:. ###: ##::: ##::
::::::::: ##:::::::. ######::::: ##:::: ##:::. ##:'####: ##::. ##:. ######:::
:::::::::..:::::::::......::::::..:::::..:::::..::....::..::::..:::......::::
"""


class TokenFormatStrings:
    @staticmethod
    def process(env: ProcessEnvironment) -> None:
        def find_fstring_spans(s):
            """
            문자열 s 내의 모든 f"…"/f'…' 리터럴의 (start, end) 인덱스를 반환.
            중첩된 중괄호를 고려하여, 같은 따옴표가 중괄호 밖에서 닫힐 때까지 찾습니다.
            """
            spans = []
            i = 0
            while i < len(s) - 1:
                if s[i] == 'f' and s[i+1] in ('"', "'"):
                    quote = s[i+1]
                    start = i
                    i += 2
                    depth = 0
                    while i < len(s):
                        c = s[i]
                        if c == '\\':       # 이스케이프 무시
                            i += 2
                            continue
                        if c == '{':
                            depth += 1
                        elif c == '}':
                            depth -= 1
                        elif c == quote and depth == 0:
                            end = i
                            spans.append((start, end))
                            break
                        i += 1
                else:
                    i += 1
            return spans

        def transform_fstring_simple(content):
            """
            f-string 내부 content 를 받아서
            - 중괄호 {…}는 (…)
            - 텍스트는 "…" 
            형태로 분리한 뒤, '+' 로 이어 붙인 문자열을 반환.
            """
            # 1) 리터럴 중괄호 처리: '{{' → ESC_L, '}}' → ESC_R
            ESC_L, ESC_R = '\x02', '\x03'
            content = content.replace('{{', ESC_L).replace('}}', ESC_R)
            segs = []
            i = 0
            while i < len(content):
                if content[i] == '{':
                    # 중괄호에 대응하는 위치 찾기
                    depth = 1
                    j = i + 1
                    while j < len(content) and depth > 0:
                        if content[j] == '{':
                            depth += 1
                        elif content[j] == '}':
                            depth -= 1
                        j += 1
                    expr = content[i+1:j-1].strip()
                    segs.append(f'{expr}')
                    i = j
                else:
                    j = i
                    while j < len(content) and content[j] != '{':
                        j += 1
                    lit = content[i:j].replace('"', r'\"')
                    # 2) ESC 토큰 복원
                    lit = lit.replace(ESC_L, '{').replace(ESC_R, '}')
                    if lit:
                        segs.append(f'"{lit}"')
                    i = j

            if not segs:
                return '""'
            return ' + '.join(segs)

        def parse_fstring(s):
            """
            s에 f"…" 또는 f'…'가 남아 있는 동안,
            find_fstring_spans 로 가장 짧은(=가장 안쪽) span 하나만 뽑아,
            transform_fstring_simple 로 교체한 뒤 반복합니다.
            최종적으로 f-string 이 전부 사라진 순수 문자열 연결식이 반환됩니다.
            """
            while True:
                spans = find_fstring_spans(s)
                if not spans:
                    break
                # 가장 짧은 span(=중첩 깊이 가장 깊은) 하나 선택
                spans.sort(key=lambda x: x[1]-x[0])
                start, end = spans[0]
                inner = s[start+2:end]            # 따옴표와 f 접두어 제외
                replaced = transform_fstring_simple(inner)
                # 바깥쪽 괄호는 맨 바깥 레벨에서만 제거하기 위해 계속 감싸두고,
                # 마지막에 한 번 껍데기 괄호를 벗겨 줍니다.
                s = s[:start] + f'{replaced}' + s[end+1:]
            # 전체가 하나의 괄호로 감싸져 있으면 벗겨 주기
            if s.startswith('(') and s.endswith(')'):
                s = s[1:-1]
            return s.replace('\\\\', '\\')

        for sourceCursor, sourceLine in enumerate(env.sourceLines):
            # f-string 변환
            processedLine = parse_fstring(sourceLine['line'])
            if processedLine != sourceLine['line']:
                env.nextLines.append(
                    {'tags': sourceLine['tags'], 'line': processedLine})
            else:
                env.nextLines.append(sourceLine)


"""
:::'###::::'########::'####::::::::::'########:'##::::'##:'########::
::'## ##::: ##.... ##:. ##::::::::::: ##.....::. ##::'##:: ##.... ##:
:'##:. ##:: ##:::: ##:: ##::::::::::: ##::::::::. ##'##::: ##:::: ##:
'##:::. ##: ########::: ##::'#######: ######:::::. ###:::: ########::
 #########: ##.....:::: ##::........: ##...:::::: ## ##::: ##.....:::
 ##.... ##: ##::::::::: ##::::::::::: ##:::::::: ##:. ##:: ##::::::::
 ##:::: ##: ##::::::::'####:::::::::: ########: ##:::. ##: ##::::::::
..:::::..::..:::::::::....:::::::::::........::..:::::..::..:::::::::
"""


class TokenApiExpression:

    @staticmethod
    def replace_api_calls(line):
        # replace '.' with '_' outside of quoted strings
        # but DO NOT replace decimal dot cases strictly bounded by non-identifier chars:
        # - 0.00
        # - .00
        # - 00.
        in_string = False
        string_char = ''
        result = []
        i = 0

        def is_ident_char(ch: str) -> bool:
            return ch.isalnum() or ch == '_'

        n = len(line)
        while i < n:
            c = line[i]
            if in_string:
                result.append(c)
                if c == string_char:
                    in_string = False
                elif c == '\\':
                    i += 1
                    if i < n:
                        result.append(line[i])
            else:
                if c == '"' or c == "'":
                    in_string = True
                    string_char = c
                    result.append(c)
                elif c == '.':
                    left_digit = (i > 0 and line[i - 1].isdigit())
                    right_digit = (i + 1 < n and line[i + 1].isdigit())

                    if left_digit or right_digit:
                        # 확장된 소수점 경계 검사
                        # 왼쪽 숫자 덩어리의 바깥 경계
                        l = i - 1
                        while l >= 0 and line[l].isdigit():
                            l -= 1
                        left_boundary = line[l] if l >= 0 else None
                        # 오른쪽 숫자 덩어리의 바깥 경계
                        r = i + 1
                        while r < n and line[r].isdigit():
                            r += 1
                        right_boundary = line[r] if r < n else None

                        preserve_decimal = True
                        # 왼쪽에 숫자가 있었다면, 그 왼쪽 바깥 경계가 식별자면 보존하지 않음
                        if left_digit and left_boundary is not None and is_ident_char(left_boundary):
                            preserve_decimal = False
                        # 오른쪽에 숫자가 있었다면, 그 오른쪽 바깥 경계가 식별자면 보존하지 않음
                        if right_digit and right_boundary is not None and is_ident_char(right_boundary):
                            preserve_decimal = False

                        if preserve_decimal:
                            result.append('.')
                        else:
                            result.append('_')
                    else:
                        result.append('_')
                else:
                    result.append(c)
            i += 1
        return ''.join(result)

    """
    replace api call expressions like LibName->Identifier with LibName_Identifier
    """
    @staticmethod
    def process(env: ProcessEnvironment) -> None:
        for sourceCursor, sourceLine in enumerate(env.sourceLines):
            # replace all occurrences of LibName->Identifier with LibName_Identifier
            # * Test->First() becomes Test_First()
            # * Test->First->Second() becomes Test_First_Second()

            processedLine = TokenApiExpression.replace_api_calls(
                sourceLine['line'])
            if processedLine != sourceLine['line']:
                env.nextLines.append(
                    {'tags': sourceLine['tags'], 'line': processedLine})
            else:
                env.nextLines.append(sourceLine)


"""
:'######:::'########:::::::::::'##::::'##::'#######::'####::'######::'########:
'##... ##:: ##.... ##:::::::::: ##:::: ##:'##.... ##:. ##::'##... ##:... ##..::
 ##:::..::: ##:::: ##:::::::::: ##:::: ##: ##:::: ##:: ##:: ##:::..::::: ##::::
 ##::'####: ########::'#######: #########: ##:::: ##:: ##::. ######::::: ##::::
 ##::: ##:: ##.... ##:........: ##.... ##: ##:::: ##:: ##:::..... ##:::: ##::::
 ##::: ##:: ##:::: ##:::::::::: ##:::: ##: ##:::: ##:: ##::'##::: ##:::: ##::::
. ######::: ########::::::::::: ##:::: ##:. #######::'####:. ######::::: ##::::
:......::::........::::::::::::..:::::..:::.......:::....:::......::::::..:::::
"""


class TokenHoistGlobalblock:
    @staticmethod
    def process(env: ProcessEnvironment) -> None:
        """
        Hoist globals~endglobals blocks to the top of their containing block (library/scope),
        preserving original order. Must run AFTER TokenLibrary/TokenScope.
        """
        inGlobalBlock = False
        globalBlockLines = []
        globalBlockTags = {}
        globalIndentLevel = 0

        def find_container_insert_pos(nextLines: list[int | dict]) -> int:
            """
            Find insertion point: right after the last 'library' or 'scope' header,
            and after any already-hoisted globals blocks under that header.
            """
            header_idx = -1
            for i, line in enumerate(nextLines):
                text = line['line']
                if text.startswith('library') or text.startswith('scope'):
                    header_idx = i
            if header_idx < 0:
                return 0
            insert_pos = header_idx + 1
            # Skip existing hoisted globals blocks (preserve order)
            i = insert_pos
            while i < len(nextLines):
                if re.match(r'^\s*globals\s*$', nextLines[i]['line']):
                    j = i + 1
                    while j < len(nextLines) and not re.match(r'^\s*endglobals\s*$', nextLines[j]['line']):
                        j += 1
                    if j < len(nextLines) and re.match(r'^\s*endglobals\s*$', nextLines[j]['line']):
                        insert_pos = j + 1
                        i = insert_pos
                        continue
                break
            return insert_pos

        def hoist_now():
            nonlocal inGlobalBlock, globalBlockLines, globalBlockTags, globalIndentLevel
            insert_pos = find_container_insert_pos(env.nextLines)
            env.nextLines.insert(insert_pos, {
                                 'tags': globalBlockTags, 'line': f'{"    "*globalIndentLevel}globals'})
            for k, globalLine in enumerate(globalBlockLines, start=1):
                env.nextLines.insert(insert_pos + k, globalLine)
            env.nextLines.insert(insert_pos + 1 + len(globalBlockLines),
                                 {'tags': globalBlockTags, 'line': f'{"    "*globalIndentLevel}endglobals'})
            inGlobalBlock = False
            globalBlockLines = []

        for sourceCursor, sourceLine in enumerate(env.sourceLines):
            # match globals statement
            match = re.match(r'^(?P<indent> *)globals\s*$', sourceLine['line'])
            if match:
                inGlobalBlock = True
                globalBlockLines = []
                globalBlockTags = sourceLine['tags']
                globalIndentLevel = len(match.group('indent')) // 4
                continue

            # match endglobals statement
            match = re.match(r'^(?P<indent> *)endglobals\s*$',
                             sourceLine['line'])
            if match and inGlobalBlock:
                hoist_now()
                continue

            if inGlobalBlock:
                # inside global block
                globalBlockLines.append(
                    {'tags': sourceLine['tags'], 'line': sourceLine['line']})
                continue

            # anything else
            env.nextLines.append(sourceLine)

        # EOF with unclosed globals: close and hoist it as well
        if inGlobalBlock:
            hoist_now()


"""
'##:::'##:'########:'##:::'##:'##:::::'##::'#######::'########::'########::
 ##::'##:: ##.....::. ##:'##:: ##:'##: ##:'##.... ##: ##.... ##: ##.... ##:
 ##:'##::: ##::::::::. ####::: ##: ##: ##: ##:::: ##: ##:::: ##: ##:::: ##:
 #####:::: ######:::::. ##:::: ##: ##: ##: ##:::: ##: ########:: ##:::: ##:
 ##. ##::: ##...::::::: ##:::: ##: ##: ##: ##:::: ##: ##.. ##::: ##:::: ##:
 ##:. ##:: ##:::::::::: ##:::: ##: ##: ##: ##:::: ##: ##::. ##:: ##:::: ##:
 ##::. ##: ########:::: ##::::. ###. ###::. #######:: ##:::. ##: ########::
..::::..::........:::::..::::::...::...::::.......:::..:::::..::........:::
"""


class TokenCustomKeywords:
    # static keyword mappings
    KEYWORD_MAPPINGS = {
        r'\sis\s+not\s': ' != ',
        r'\sis\s': ' == ',
        r'\bnone\b': '0',
        r'\bpass\b': 'return',
        r'\bexit\b': 'return',
    }

    @staticmethod
    def process(env: ProcessEnvironment) -> None:
        def replace_outside_quotes(line, keyword_mappings):
            in_string = False
            string_char = ''
            result = ''
            i = 0

            while i < len(line):
                c = line[i]
                if in_string:
                    result += c
                    if c == string_char and (i == 0 or line[i - 1] != '\\'):
                        in_string = False
                    elif c == '\\' and i + 1 < len(line):
                        result += line[i + 1]
                        i += 1
                else:
                    if c in ('"', "'"):
                        in_string = True
                        string_char = c
                        result += c
                    else:
                        replaced = False
                        for pattern, replacement in keyword_mappings.items():
                            m = re.match(pattern, line[i:])
                            if m:
                                result += replacement
                                # FIX: advance by matched text length, not pattern length
                                i += len(m.group(0)) - 1
                                replaced = True
                                break
                        if not replaced:
                            result += c
                i += 1
            return result

        for sourceCursor, sourceLine in enumerate(env.sourceLines):
            processedLine = replace_outside_quotes(
                sourceLine['line'], TokenCustomKeywords.KEYWORD_MAPPINGS)
            if processedLine != sourceLine['line']:
                env.nextLines.append(
                    {'tags': sourceLine['tags'], 'line': processedLine})
            else:
                env.nextLines.append(sourceLine)


"""
'##::::'##::::'###::::'####:'##::: ##:
 ###::'###:::'## ##:::. ##:: ###:: ##:
 ####'####::'##:. ##::: ##:: ####: ##:
 ## ### ##:'##:::. ##:: ##:: ## ## ##:
 ##. #: ##: #########:: ##:: ##. ####:
 ##:.:: ##: ##.... ##:: ##:: ##:. ###:
 ##:::: ##: ##:::: ##:'####: ##::. ##:
..:::::..::..:::::..::....::..::::..::
"""

if __name__ == "__main__":
    compile()
