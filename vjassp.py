#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert vJASS+ into vJASS code
Version: 3.0
"""

import os
import re
import sys
import uuid

# generate 16 width uppercase UUID


def generateUUID():
    return str(uuid.uuid4()).replace('-', '').upper()[:16]


def normalizePath(sourceFilePath):
    return os.path.abspath(sourceFilePath.replace('\\', '/'))


if __name__ == "__main__":
    # if there is no argument, print usage
    if len(sys.argv) < 2:
        print("Usage: python vjassp.py <source_path>")
        sys.exit(1)

    # get the source path from the argument
    entryPath = normalizePath(sys.argv[1])

    # Step 1: Initialize the source group
    sourceGroup = {
        entryPath: {
            'compiled': False,
        }
    }

    # Step 2: Compile until all source files are compiled
    finalLines = []
    while True:
        # Step 2.1: Find all source files that are not compiled
        sourceFiles = [path for path,
                       info in sourceGroup.items() if not info['compiled']]
        if not sourceFiles:
            break

        # Step 2.2: Compile each source file
        for sourcePath in sourceFiles:
            # Read the source file
            with open(sourcePath, 'r', encoding='utf-8') as file:
                sourceLines = [{'tags': {}, 'line': sourceLine}
                               for sourceLine in file.read().splitlines()]

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

            def processComment():
                multiCommentBlock = False
                for sourceLine in sourceLines:
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
                    nextLines.append(sourceLine)

            nextLines = []
            processComment()
            sourceLines = nextLines

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

            def processImport():
                for sourceLine in sourceLines:
                    # single-line import statement
                    match = re.match(
                        r'^\s*import\s+([a-zA-Z0-9_-][a-zA-Z0-9_.-]*)\s*$', sourceLine['line'])
                    if match:
                        importPath = match.group(1).replace('.', '/')
                        importPath = os.path.join(
                            os.path.dirname(sourcePath), importPath)
                        importPath = normalizePath(importPath) + '.jp'
                        if importPath not in sourceGroup:
                            sourceGroup[importPath] = {
                                'compiled': False,
                            }
                        continue
                    # anything else
                    nextLines.append(sourceLine)

            nextLines = []
            processImport()
            sourceLines = nextLines

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

            def processType():
                for sourceCursor, sourceLine in enumerate(sourceLines):
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

                        nextLines.append(
                            {'tags': {}, 'line': f'{typeIndent}{typeModifier}struct {typeName}{typeExtends}'})
                        nextLines.append({'tags': {}, 'line': f'{typeIndent}endstruct'})
                        continue

                    # anything else
                    nextLines.append(sourceLine)

            nextLines = []
            processType()
            sourceLines = nextLines

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

            def processInitFunc():
                initFunctionBlock = False
                initFunctionIndentLevel = 0
                for sourceLine in sourceLines:
                    # check exiting init block
                    if initFunctionBlock:
                        match = re.match(r'^(?P<indent> *)', sourceLine['line'])
                        if match:
                            indentLevel = len(match.group('indent')) // 4
                            if indentLevel <= initFunctionIndentLevel:
                                # exiting init block
                                nextLines.append(
                                    {'tags': {}, 'line': f'{"    "*initFunctionIndentLevel}endfunction'})
                                initFunctionBlock = False
                            else:
                                # inside init block
                                sourceLine['tags']['function'] = True
                                nextLines.append(sourceLine)
                                continue

                    # init: block
                    match = re.match(
                        r'^(?P<indent> *)init\s*:\s*$', sourceLine['line'])
                    if match:
                        initFunctionBlock = True
                        indent = match.group('indent')
                        initFunctionIndentLevel = len(indent) // 4
                        functionName = f'VJPI{generateUUID()}'
                        nextLines.append(
                            {'tags': {'init': True}, 'line': f'{indent}private function {functionName} takes nothing returns nothing'})
                        continue

                    # anything else
                    nextLines.append(sourceLine)

                if initFunctionBlock:
                    # if the init block is not closed, close it
                    nextLines.append(
                        {'tags': {}, 'line': f'{"    "*initFunctionIndentLevel}endfunction'})
                    initFunctionBlock = False

            nextLines = []
            processInitFunc()
            sourceLines = nextLines

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
            def processRequire():
                for sourceCursor, sourceLine in enumerate(sourceLines):
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
                        nextLines.append(sourceLine)
                        continue

                    # anything else
                    nextLines.append(sourceLine)

            nextLines = []
            processRequire()
            sourceLines = nextLines

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

            def processLibrary():
                libraryInfo = None
                inLibrary = False

                def finalizeLibraryBlock(libraryInfo):
                    nonlocal inLibrary
                    requireStatement = ''
                    if libraryInfo['requires']:
                        requireStatement = f' requires {', '.join(libraryInfo["requires"])}'

                    if libraryInfo['inits']:
                        # if libraryInfo['inits'] is not empty:
                        nextLines.insert(
                            libraryInfo['cursor'], {'tags': {}, 'line': f'library {libraryInfo["name"]} initializer onInit{requireStatement}'})
                        nextLines.append(
                            {'tags': {'library': True}, 'line': f'    private function onInit takes nothing returns nothing'})
                        for initFuncName in libraryInfo['inits']:
                            nextLines.append({'tags': {'library': True, 'function': True}, 'line': f'        call {initFuncName}()'})
                        nextLines.append({'tags': {'library': True}, 'line': '    endfunction'})
                    else:
                        nextLines.insert(
                            libraryInfo['cursor'], {'tags': {}, 'line': f'library {libraryInfo["name"]}{requireStatement}'})
                    nextLines.append({'tags': {}, 'line': 'endlibrary'})
                    inLibrary = False

                for sourceCursor, sourceLine in enumerate(sourceLines):
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
                            'cursor': len(nextLines),
                            'name': match.group('libraryName'),
                            'inits': [],
                            'requires': [],
                        }
                        inLibrary = True
                        continue

                    # initializer support - 태그 기반 검사로 변경
                    if sourceLine['tags'].get('init', False) and libraryInfo is not None:
                        initFuncMatch = re.match(r'^ *private function\s+([a-zA-Z0-9_-][a-zA-Z0-9_.-]*)\s+', sourceLine['line'])
                        if initFuncMatch:
                            initFuncName = initFuncMatch.group(1)
                            libraryInfo['inits'].append(initFuncName)
                            sourceLine['tags']['library'] = True
                            nextLines.append(sourceLine)
                            continue

                    # require support - 태그 기반 검사로 변경
                    if sourceLine['tags'].get('require', False) and libraryInfo is not None:
                        libraryInfo['requires'].append(sourceLine['tags']['require'])
                        # actual require line is not needed in the library block
                        continue

                    # anything else
                    if inLibrary:
                        sourceLine['tags']['library'] = True
                    nextLines.append(sourceLine)

                if libraryInfo is not None:
                    # if the library block is not closed, close it
                    finalizeLibraryBlock(libraryInfo)

            nextLines = []
            processLibrary()
            sourceLines = nextLines

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

            def processContent():
                contentInfo = None
                inContent = False

                def finalizeContentBlock(contentInfo):
                    nonlocal inContent
                    if contentInfo['inits']:
                        # if contentInfo['inits'] is not empty:
                        nextLines.insert(
                            contentInfo['cursor'], {'tags': {}, 'line': f'scope {contentInfo["name"]} initializer onInit'})
                        nextLines.append(
                            {'tags': {'content': True}, 'line': f'    private function onInit takes nothing returns nothing'})
                        for initFuncName in contentInfo['inits']:
                            nextLines.append({'tags': {'content': True, 'function': True}, 'line': f'        call {initFuncName}()'})
                        nextLines.append({'tags': {'content': True}, 'line': '    endfunction'})
                    else:
                        nextLines.insert(
                            contentInfo['cursor'], {'tags': {}, 'line': f'scope {contentInfo["name"]}'})
                    nextLines.append({'tags': {}, 'line': 'endscope'})
                    inContent = False

                for sourceCursor, sourceLine in enumerate(sourceLines):
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
                            'cursor': len(nextLines),
                            'name': contentName,
                            'inits': [],
                        }
                        inContent = True
                        continue

                    # initializer support - 태그 기반 검사로 변경
                    if sourceLine['tags'].get('init', False) and contentInfo is not None:
                        initFuncMatch = re.match(r'^ *private function\s+([a-zA-Z0-9_-][a-zA-Z0-9_.-]*)\s+', sourceLine['line'])
                        if initFuncMatch:
                            initFuncName = initFuncMatch.group(1)
                            contentInfo['inits'].append(initFuncName)
                            sourceLine['tags']['content'] = True
                            nextLines.append(sourceLine)
                            continue

                    # anything else
                    if inContent:
                        sourceLine['tags']['content'] = True
                    nextLines.append(sourceLine)

                if contentInfo is not None:
                    # if the content block is not closed, close it
                    finalizeContentBlock(contentInfo)

            nextLines = []
            processContent()
            sourceLines = nextLines

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

            def processFunction():
                functionInfo = None

                for sourceCursor, sourceLine in enumerate(sourceLines):
                    # check function block end
                    if functionInfo is not None:
                        match = re.match(r'^(?P<indent> *)', sourceLine['line'])
                        if match:
                            indentLevel = len(match.group('indent')) // 4
                            if indentLevel <= functionInfo['indentLevel']:
                                # exiting function block
                                nextLines.append(
                                    {'tags': {}, 'line': f'{"    "*functionInfo["indentLevel"]}endfunction'})
                                functionInfo = None
                            else:
                                # inside function block
                                sourceLine['tags']['function'] = True
                                nextLines.append(sourceLine)
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
                        nextLines.append(
                            {'tags': sourceLine['tags'], 'line': f'{functionIndent}{functionModifier}function {functionInfo["name"]} takes {functionInfo["takes"]} returns {functionInfo["returns"]}'})
                        continue

                    # anything else
                    nextLines.append(sourceLine)

            nextLines = []
            processFunction()
            sourceLines = nextLines

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

            def processVariable():
                globalBlock = False
                globalTags = None
                globalIndentLevel = 0
                for sourceCursor, sourceLine in enumerate(sourceLines):
                    # variable statement
                    match = re.match(
                        r'^(?P<indent> *)(?:(?P<modifier>api|global)\s+)?(?P<type>[a-zA-Z][a-zA-Z0-9]*)\s+(?P<let>\*)?(?P<name>[a-zA-Z][a-zA-Z0-9_]*)(?:\s*=\s*(?P<value>.*?))?\s*$', sourceLine['line'])
                    if match and not re.match(r'\b(return)\b', match.group('type')):
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
                                match = re.match(r'^(?P<indent> *)', sourceLine['line'])
                                if match:
                                    indentLevel = len(match.group('indent')) // 4
                                    globalIndentLevel = indentLevel
                                    globalTags = sourceLine['tags']
                                    nextLines.append(
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
                            

                        nextLines.append({'tags': sourceLine['tags'], 'line': variableResult})
                        continue

                    # anything else
                    if globalBlock:
                        match = re.match(r'^(?P<indent> *)', sourceLine['line'])
                        if match:
                            indentLevel = len(match.group('indent')) // 4
                            if indentLevel <= globalIndentLevel:
                                # exiting global block
                                nextLines.append(
                                    {'tags': globalTags, 'line': f'{"    "*globalIndentLevel}endglobals'})
                                globalBlock = False
                            else:
                                # inside global block
                                sourceLine['tags']['global'] = True
                                nextLines.append(sourceLine)
                                continue

                    nextLines.append(sourceLine)

                if globalBlock:
                    # if the global block is not closed, close it
                    nextLines.append(
                        {'tags': globalTags, 'line': f'{"    "*globalIndentLevel}endglobals'})
                    globalBlock = False

            nextLines = []
            processVariable()
            sourceLines = nextLines

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

            def processLoopBlock():
                loopBlockStack = []
                for sourceCursor, sourceLine in enumerate(sourceLines):
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
                        nextLines.append(
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
                        nextLines.append(
                            {'tags': sourceLine['tags'], 'line': f'{loopIndent}loop'})
                        nextLines.append(
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
                        nextLines.append(
                            {'tags': sourceLine['tags'], 'line': f'{loopIndent}loop'})
                        nextLines.append(
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
                    #         nextLines.append(
                    #             {'tags': sourceLine['tags'], 'line': f'{loopIndent}set {withValue} = {fromValue}'})
                    #         nextLines.append(
                    #             {'tags': sourceLine['tags'], 'line': f'{loopIndent}local integer vjsr_{withValue}_{generateUUID()} = {fromValue}'})
                    #     else:
                    #         nextLines.append(
                    #             {'tags': sourceLine['tags'], 'line': f'{loopIndent}local integer {withValue} = {fromValue}'})
                    #     # append loop block
                    #     nextLines.append(
                    #         {'tags': sourceLine['tags'], 'line': f'{loopIndent}loop'})

                    # anything else but was in loop block
                    if len(loopBlockStack) > 0:
                        # pop loop block until the indent level is less than the current line
                        while len(loopBlockStack) > 0:
                            loopBlock = loopBlockStack[-1]
                            match = re.match(r'^(?P<indent> *)', sourceLine['line'])
                            if match:
                                indentLevel = len(match.group('indent')) // 4
                                if indentLevel <= loopBlock['indentLevel']:
                                    # exiting loop block
                                    nextLines.append(
                                        {'tags': {}, 'line': f'{"    "*loopBlock["indentLevel"]}endloop'})
                                    loopBlockStack.pop()
                                    continue
                                else:
                                    break

                    # anything else
                    nextLines.append(sourceLine)

                while len(loopBlockStack) > 0:
                    # if the loop block is not closed, close it
                    loopBlock = loopBlockStack.pop()
                    nextLines.append(
                        {'tags': {}, 'line': f'{"    "*loopBlock["indentLevel"]}endloop'})
                    loopBlockStack = []

            nextLines = []
            processLoopBlock()
            sourceLines = nextLines

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

            def processIfBlock():
                ifBlockStack = []
                for sourceCursor, sourceLine in enumerate(sourceLines):
                    # match if condition_expression: block
                    match = re.match(
                        r'^(?P<indent> *)if\s+(?P<condition>.*?):\s*$', sourceLine['line'])
                    if match:
                        ifIndent = match.group('indent')
                        ifIndentLevel = len(ifIndent) // 4
                        ifBlockStack.append({
                            'cursor': sourceCursor,
                            'indentLevel': ifIndentLevel,
                            'tags': sourceLine['tags'],
                        })
                        conditionExpression = match.group('condition')
                        nextLines.append(
                            {'tags': sourceLine['tags'], 'line': f'{ifIndent}if {conditionExpression} then'})
                        continue

                    # match elseif condition_expression: block

                    # anything else but was in if block
                    if len(ifBlockStack) > 0:
                        # pop loop block until the indent level is less than the current line
                        while len(ifBlockStack) > 0:
                            ifBlock = ifBlockStack[-1]
                            match = re.match(r'^(?P<indent> *)', sourceLine['line'])
                            if match:
                                indentLevel = len(match.group('indent')) // 4
                                if indentLevel <= ifBlock['indentLevel']:
                                    # exiting loop block
                                    nextLines.append(
                                        {'tags': ifBlock['tags'], 'line': f'{"    "*ifBlock["indentLevel"]}endif'})
                                    ifBlockStack.pop()
                                    continue
                                else:
                                    break

                    # anything else
                    nextLines.append(sourceLine)

                while len(ifBlockStack) > 0:
                    # if the loop block is not closed, close it
                    ifBlock = ifBlockStack.pop()
                    nextLines.append(
                        {'tags': {}, 'line': f'{"    "*ifBlock["indentLevel"]}endif'})
                    ifBlockStack

            nextLines = []
            processIfBlock()
            sourceLines = nextLines

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

            def processCodePrefix():
                """
                within lines that have 'function' tag, we need to ensure that each line starts with proper prefix
                automatically add 'call' to the function call statement
                and automatically add 'set' to the variable assignment statement
                """
                for sourceLine in sourceLines:
                    # check if the line is a function call or variable assignment
                    if sourceLine['tags'].get('function', False):
                        # function call
                        match = re.match(r'^(?P<indent> *)(?P<name>[a-zA-Z][a-zA-Z0-9_.\[\]]*\s*\(.*?\))\s*$', sourceLine['line'])
                        if match:
                            functionIndent = match.group('indent')
                            functionName = match.group('name')
                            nextLines.append(
                                {'tags': sourceLine['tags'], 'line': f'{functionIndent}call {functionName}'})
                            continue

                        # variable assignment
                        match = re.match(r'^(?P<indent> *)(?P<name>[a-zA-Z][a-zA-Z0-9_.\[\]]*)\s*(?P<operator>=|\+\+|\-\-|\*\*|//|\+=|\-=|\*=|/=)\s*(?P<value>.*)$', sourceLine['line'])
                        if match:
                            variableIndent = match.group('indent')
                            variableName = match.group('name')
                            variableValue = match.group('value')
                            variableOperator = match.group('operator')

                            if variableOperator == '=':
                                nextLines.append(
                                    {'tags': sourceLine['tags'], 'line': f'{variableIndent}set {variableName} = {variableValue}'})
                            elif variableOperator == '++':
                                nextLines.append(
                                    {'tags': sourceLine['tags'], 'line': f'{variableIndent}set {variableName} = {variableName} + 1'})
                            elif variableOperator == '--':
                                nextLines.append(
                                    {'tags': sourceLine['tags'], 'line': f'{variableIndent}set {variableName} = {variableName} - 1'})
                            elif variableOperator == '**':
                                nextLines.append(
                                    {'tags': sourceLine['tags'], 'line': f'{variableIndent}set {variableName} = {variableName} * 2'})
                            elif variableOperator == '//':
                                nextLines.append(
                                    {'tags': sourceLine['tags'], 'line': f'{variableIndent}set {variableName} = {variableName} / 2'})
                            elif variableOperator == '+=':
                                nextLines.append(
                                    {'tags': sourceLine['tags'], 'line': f'{variableIndent}set {variableName} = {variableName} + {variableValue}'})
                            elif variableOperator == '-=':
                                nextLines.append(
                                    {'tags': sourceLine['tags'], 'line': f'{variableIndent}set {variableName} = {variableName} - {variableValue}'})
                            elif variableOperator == '*=':
                                nextLines.append(
                                    {'tags': sourceLine['tags'], 'line': f'{variableIndent}set {variableName} = {variableName} * {variableValue}'})
                            elif variableOperator == '/=':
                                nextLines.append(
                                    {'tags': sourceLine['tags'], 'line': f'{variableIndent}set {variableName} = {variableName} / {variableValue}'})
                            else:
                                # unknown operator, just append the line as is
                                nextLines.append(sourceLine)
                            continue

                    # anything else
                    nextLines.append(sourceLine)

            nextLines = []
            processCodePrefix()
            sourceLines = nextLines

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

            def processHoisting():
                """
                In vJass, all local variables must be declared at the beginning of the function.
                This function will hoist all local variable declarations to the top of the function block.
                and leave assignments in the original place. (if possible)
                """
                hoistPositionStack = []

                for sourceCursor, sourceLine in enumerate(sourceLines):
                    # check if we met a function statement
                    match = re.match(r'^(?P<indent> *)(?:(?P<modifier>private|public)\s+)?function\s+(?P<name>[a-zA-Z][a-zA-Z0-9]*)', sourceLine['line'])
                    if match:
                        hoistPositionStack.append({
                            'cursor': len(nextLines),
                            'indentLevel': len(match.group('indent')) // 4,
                            'tags': sourceLine['tags'],
                        })
                        nextLines.append(sourceLine)
                        continue

                    # if hoistPositionStack is not empty, and we met lower or equal indent level, we need to pop the stack
                    if len(hoistPositionStack) > 0:
                        match = re.match(r'^(?P<indent> *)', sourceLine['line'])
                        indentLevel = len(match.group('indent')) // 4
                        while len(hoistPositionStack) > 0 and indentLevel <= hoistPositionStack[-1]['indentLevel']:
                            hoistPositionStack.pop()

                    # check if we met a local variable declaration
                    match = re.match(
                        r'^(?P<indent> *)local\s+(?P<constant>constant\s+)?(?P<type>[a-zA-Z][a-zA-Z0-9]*)\s+(?:(?P<array>array)\s+)?(?P<name>[a-zA-Z][a-zA-Z0-9_]*)(?:\s*=\s*(?P<value>.*?))?\s*$', sourceLine['line'])
                    if match:
                        # check if we need hoist this variable
                        # -- if hoistPositionStack is not empty and the cursor is right after the hoist position, we dont need to hoist this variable
                        if len(hoistPositionStack) > 0 and len(nextLines) == hoistPositionStack[-1]['cursor'] + 1:
                            # update the hoist position to the next line
                            hoistPositionStack[-1]['cursor'] += 1
                            nextLines.append(sourceLine)
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

                        nextLines.insert(
                            hoistPositionStack[-1]['cursor'] + 1, {'tags': sourceLine['tags'], 'line': hoistCode})
                        hoistPositionStack[-1]['cursor'] += 1

                        # if the variable has an assignment, we need to add it to the next line
                        if not variableConstant and variableValue:
                            nextLines.append(
                                {'tags': sourceLine['tags'], 'line': f'{variableIndent}set {variableName} = {variableValue}'})
                        continue

                    # anything else
                    nextLines.append(sourceLine)



            nextLines = []
            processHoisting()
            sourceLines = nextLines


            # mark as compiled
            # import json
            # print(json.dumps(sourceLines, indent=4, ensure_ascii=False))
            for sourceLine in sourceLines:
                finalLines.append(sourceLine['line'])
            sourceGroup[sourcePath]['compiled'] = True

    # write the final text to a file with same directory with .j extension
    finalPath = os.path.splitext(entryPath)[0] + '.j'
    with open(finalPath, 'w', encoding='utf-8') as file:
        file.write('\n'.join(finalLines))
    print(f'Compiled source saved to {finalPath}')
