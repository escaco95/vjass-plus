#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert vJASS+ into vJASS code
Version: 3.021

Change Log:
- 3.02: Added mass import (.*/.**) syntax
  - 3.021: Fixed variable syntax regex including library/scope/content
"""

import os
import re
import sys
import uuid

class DslSyntaxError(Exception):
    """
    Exception raised for syntax errors in the DSL.
    """
    def __init__(self, filePath, lineNumber, lineText, message):
        super().__init__(message)
        self.filePath = filePath
        self.lineNumber = lineNumber
        self.lineText = lineText
        self.message = message
    
    def __str__(self):
        return f'File "{self.filePath}", line {self.lineNumber}\n{self.message}'

def generateUUID():
    """
    Generate a 16 width uppercase UUID.
    """
    return str(uuid.uuid4()).replace('-', '').upper()[:16]


def normalizePath(sourceFilePath):
    return os.path.abspath(sourceFilePath.replace('\\', '/'))


# token processor
tokenProcessors = []


class ProcessEnvironment:
    def __init__(self):
        self.sourceGroup = {}
        self.sourceLines = []
        self.nextLines = []
        self.arguments = {}
        self.sourcePath = None

    def containsArgument(self, argument: str) -> bool:
        return argument in self.arguments and self.arguments[argument] is not None


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

    # Step 1: Initialize the source group
    env = ProcessEnvironment()
    env.sourceGroup = {
        entryPath: {
            'compiled': False,
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

    # Step 2: Compile until all source files are compiled
    finalLines = []
    while True:
        # Step 2.1: Find all source files that are not compiled
        sourceFiles = [path for path,
                       info in env.sourceGroup.items() if not info['compiled']]
        if not sourceFiles:
            break

        # Step 2.2: Compile each source file
        for sourcePath in sourceFiles:
            env.sourcePath = sourcePath
            # Read the source file
            with open(sourcePath, 'r', encoding='utf-8') as file:
                env.sourceLines = [{'tags': {}, 'line': sourceLine}
                                   for sourceLine in file.read().splitlines()]

            try:
                for tokenProcessor in tokenProcessors:
                    env.nextLines = []
                    tokenProcessor(env)
                    env.sourceLines = env.nextLines
            except DslSyntaxError as e:
                print(f'Syntax Error (most recent call last):')
                print(f'  {e}')
                sys.exit(1)
            except Exception as e:
                raise e

            # mark as compiled
            for sourceLine in env.sourceLines:
                finalLines.append(sourceLine['line'])
            env.sourceGroup[sourcePath]['compiled'] = True

    # print post compile environment
    print('  Imported files:')
    for index, importPath in enumerate(env.sourceGroup.keys()):
        print(f'    File "{importPath}" ({index + 1})')

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


def processComment(env: ProcessEnvironment) -> None:
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
        # single-line comment
        match = re.match(r'^\s*#.*$', sourceLineText)
        if match:
            continue
        # empty line
        match = re.match(r'^\s*$', sourceLineText)
        if match:
            continue
        # anything else
        env.nextLines.append(sourceLine)


tokenProcessors.append(processComment)

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


def processImport(env: ProcessEnvironment) -> None:
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
                        env.sourcePath, sourceCursor + 1, sourceLine, f'No such Directory "{importPath}"')
                # if mass import, and mass option is .*, add all files in the directory
                if importMass == '.*':
                    for root, dirs, files in os.walk(importPath):
                        for file in files:
                            if file.endswith('.jp'):
                                # remove .jp extension
                                file = file[:-3]
                                # normalize path
                                file = normalizePath(os.path.join(root,file))
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
                                    file = normalizePath(os.path.join(root,file))
                                    # append .jp extension
                                    file += '.jp'
                                    importPaths.append(file)
                            # add subdirs to the list
                            for dir in dirs:
                                recursiveDirs.append(os.path.join(root, dir))
            for importPath in importPaths:
                if importPath not in env.sourceGroup:
                    # if file not exists, raise syntax error
                    if not os.path.exists(importPath):
                        raise DslSyntaxError(
                            env.sourcePath, sourceCursor + 1, sourceLine, f'No such File "{importPath}"')
                    # add to the source group
                    env.sourceGroup[importPath] = {
                        'compiled': False,
                    }
            continue
        # anything else
        env.nextLines.append(sourceLine)


tokenProcessors.append(processImport)

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


def processType(env: ProcessEnvironment) -> None:
    for sourceLine in env.sourceLines:
        # type statement
        match = re.match(
            r'^(?P<indent> *)(?:(?P<modifier>api|global)\s+)?type\s+(?P<typeName>[a-zA-Z0-9_-][a-zA-Z0-9_.-]*)\s+extends\s+(?P<extends>[a-zA-Z0-9_-][a-zA-Z0-9_.-]*)\s*$', sourceLine['line'])
        if match:
            typeIndent = match.group('indent')
            typeModifier = match.group('modifier')
            if typeModifier == 'api':
                typeModifier = 'public '
            elif typeModifier == 'global':
                typeModifier = ''
            else:
                typeModifier = 'private '
            typeName = match.group('typeName')
            typeExtends = match.group('extends')
            if typeExtends == 'handle':
                typeExtends = ''
            else:
                typeExtends = ' extends array'

            env.nextLines.append(
                {'tags': {}, 'line': f'{typeIndent}{typeModifier}struct {typeName}{typeExtends}'})
            env.nextLines.append(
                {'tags': {}, 'line': f'{typeIndent}endstruct'})
            continue

        # anything else
        env.nextLines.append(sourceLine)


tokenProcessors.append(processType)


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


def processInitFunc(env: ProcessEnvironment) -> None:
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
                        {'tags': {}, 'line': f'{"    "*initFunctionIndentLevel}endfunction'})
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
                {'tags': {'init': True}, 'line': f'{indent}private function {functionName} takes nothing returns nothing'})
            continue

        # anything else
        env.nextLines.append(sourceLine)

    if initFunctionBlock:
        # if the init block is not closed, close it
        env.nextLines.append(
            {'tags': {}, 'line': f'{"    "*initFunctionIndentLevel}endfunction'})
        initFunctionBlock = False


tokenProcessors.append(processInitFunc)


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


def processRequire(env: ProcessEnvironment) -> None:
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


tokenProcessors.append(processRequire)

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


def processLibrary(env: ProcessEnvironment) -> None:
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
            r'^(?P<indent> *)library\s+(?P<libraryName>[a-zA-Z0-9_-][a-zA-Z0-9_.-]*)\s*:\s*$', sourceLine['line'])
        if match:
            libraryInfo = {
                'indentLevel': len(match.group('indent')) // 4,
                'cursor': len(env.nextLines),
                'name': match.group('libraryName'),
                'inits': [],
                'requires': [],
            }
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


tokenProcessors.append(processLibrary)

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


def processContent(env: ProcessEnvironment) -> None:
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


tokenProcessors.append(processContent)

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


def processNative(env: ProcessEnvironment) -> None:
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


tokenProcessors.append(processNative)

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


def processFunction(env: ProcessEnvironment) -> None:
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
            r'^(?P<indent> *)(?:(?P<modifier>api|global)\s+)?(?P<name>[a-zA-Z][a-zA-Z0-9]*)\s*\((?P<takes>[^)]*)\)(?:\s*->\s*(?P<returns>\w+))?\s*:$', sourceLine['line'])
        if match:
            functionIndent = match.group('indent')
            functionModifier = match.group('modifier')
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
                'name': match.group('name'),
                'takes': functionTakes,
                'returns': functionReturns,
            }
            env.nextLines.append(
                {'tags': sourceLine['tags'], 'line': f'{functionIndent}{functionModifier}function {functionInfo["name"]} takes {functionInfo["takes"]} returns {functionInfo["returns"]}'})
            continue

        # anything else
        env.nextLines.append(sourceLine)


tokenProcessors.append(processFunction)

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


def processVariable(env: ProcessEnvironment) -> None:
    globalBlock = False
    globalTags = None
    globalIndentLevel = 0
    for sourceCursor, sourceLine in enumerate(env.sourceLines):
        # variable statement
        match = re.match(
            r'^(?P<indent> *)(?:(?P<modifier>api|global)\s+)?(?P<type>[a-zA-Z][a-zA-Z0-9]*)\s+(?P<let>\*)?(?P<name>[a-zA-Z][a-zA-Z0-9_]*)(?:\s*=\s*(?P<value>.*?))?\s*$', sourceLine['line'])
        if match and not re.match(r'\b(library|scope|content|return|if|elseif|else|loop|while|until)\b', match.group('type')):
            variableIndent = match.group('indent')
            variableModifier = match.group('modifier')
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


tokenProcessors.append(processVariable)

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


def processLoopBlock(env: ProcessEnvironment) -> None:
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

        # anything else
        env.nextLines.append(sourceLine)

    while len(loopBlockStack) > 0:
        # if the loop block is not closed, close it
        loopBlock = loopBlockStack.pop()
        env.nextLines.append(
            {'tags': {}, 'line': f'{"    "*loopBlock["indentLevel"]}endloop'})
        loopBlockStack = []


tokenProcessors.append(processLoopBlock)

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


def processIfBlock(env: ProcessEnvironment) -> None:
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


tokenProcessors.append(processIfBlock)

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


def processCodePrefix(env: ProcessEnvironment) -> None:
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


tokenProcessors.append(processCodePrefix)

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


def processHoisting(env: ProcessEnvironment) -> None:
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


tokenProcessors.append(processHoisting)

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
