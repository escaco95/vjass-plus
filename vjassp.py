#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert vJASS+ into vJASS code
Python Version: 3.12
vJASS+ Version: 3.201

Author: choi-sw (escaco95@naver.com)

Change Log:
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
    while True:
        # Step 1.91: Find all source files that are not preprocessed
        sourceFiles = [path for path,
                       info in env.sourceGroup.items() if not info.get('preprocessed', False)]
        if not sourceFiles:
            break

        # Step 1.92: Preprocess each source file
        for sourcePath in sourceFiles:
            env.sourcePath = sourcePath
            # Read the source file
            with open(sourcePath, 'r', encoding='utf-8') as file:
                env.sourceLines = [{'tags': {}, 'cursor': sourceCursor, 'line': sourceLine}
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
    # Step 4.1: append empty line if the last line is not empty
    if not finalLines[-1].endswith('\n'):
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
    @staticmethod
    def preprocess(env: ProcessEnvironment) -> None:
        for sourceCursor, sourceLine in enumerate(env.sourceLines):
            # single-line import statement
            match = re.match(
                r'^\s*(?:when\s+(?P<when>[a-zA-Z0-9_.-]+)\s+)?import\s+(?P<import>[a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9_-]+)*)(?P<mass>\.\*\*?)?\s*$', sourceLine['line'])
            if match:
                # check when statement
                importWhen = match.group('when')
                if importWhen is not None and not env.containsArgument(importWhen):
                    # if when statement is not in arguments, skip this import statement
                    continue

                importPath = match.group('import').replace('.', '/')
                importPath = os.path.join(
                    os.path.dirname(env.sourcePath), importPath)
                importPath = normalizePath(importPath)

                importPaths = []
                # if not mass import, add .jp extension
                importMass = match.group('mass')
                if importMass is None:
                    importPath += '.jp'
                    importPaths.append(importPath)
                else:
                    # if directory not exists, raise syntax error
                    if not os.path.isdir(importPath):
                        raise DslSyntaxError(
                            env.sourcePath, sourceLine['cursor'], sourceLine, f'No such Directory "{importPath}"')
                    # if mass import, and mass option is .*, add all files in the directory
                    if importMass == '.*':
                        for root, dirs, files in os.walk(importPath):
                            for file in files:
                                if file.endswith('.jp'):
                                    # remove .jp extension
                                    file = file[:-3]
                                    # normalize path
                                    file = normalizePath(
                                        os.path.join(root, file))
                                    # append .jp extension
                                    file += '.jp'
                                    importPaths.append(file)
                    elif importMass == '.**':
                        # double star import = recursive import
                        recursiveDirs = [importPath]
                        while recursiveDirs:
                            currentDir = recursiveDirs.pop()
                            for root, dirs, files in os.walk(currentDir):
                                for file in files:
                                    if file.endswith('.jp'):
                                        # remove .jp extension
                                        file = file[:-3]
                                        # normalize path
                                        file = normalizePath(
                                            os.path.join(root, file))
                                        # append .jp extension
                                        file += '.jp'
                                        importPaths.append(file)
                                # add subdirs to the list
                                for dir in dirs:
                                    recursiveDirs.append(
                                        os.path.join(root, dir))
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
                    macroArgs = [arg.strip() for arg in re.split(r',(?=(?:[^"]*"[^"]*")*[^"]*$)', macroArgs)]
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
                    macroArgs = [arg.strip() for arg in re.split(r',(?=(?:[^"]*"[^"]*")*[^"]*$)', macroArgs)]
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
                        sourceLine['tags']['function'] = True
                        env.nextLines.append(sourceLine)
                        continue

            # function statement
            match = re.match(
                r'^(?P<indent> *)(?:(?P<modifier>api|global)\s+)?(?P<name>[a-zA-Z][a-zA-Z0-9_]*)\s*\((?P<takes>[^)]*)\)(?:\s*->\s*(?P<returns>\w+))?\s*:\s*$', sourceLine['line'])
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
                r'^(?P<indent> *)(?:(?P<modifier>api|global)\s+)?(?P<type>[a-zA-Z][a-zA-Z0-9]*)\s+(?P<let>\*)?(?P<name>[a-zA-Z][a-zA-Z0-9_]*)(?:\s*=\s*(?P<value>.*?))?\s*$', sourceLine['line'])
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
                variableLet = match.group('let')
                variableType = match.group('type')
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
                    r'^(?P<indent> *)(?P<name>[a-zA-Z][a-zA-Z0-9_.\[\]]*)\s*(?P<operator>=|\+\+|\-\-|\*\*|//|\+=|\-=|\*=|/=)\s*(?P<value>.*)$', sourceLine['line'])
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
