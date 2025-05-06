# vjass-plus
a vJASS DSL

## vJass+ Form

```
library tick:

    integer     INITIAL_TICK_INSTANCES  = 1000
    hashtable   TABLE                   = {}
    timer       *timers                 = []
    integer     *lastCreated
    
    init:
        integer *i = 1
        until i > INITIAL_TICK_INSTANCES:
            timers[i] = CreateTimer()
            SaveInteger(TABLE, 0, GetHandleId(timers[i]), i)
            i++
    
    type tickindexer extends handle
    global type tick extends integer

    global TickCreate() -> tick:
        lastCreated = tickindexer.create()
        if timers[lastCreated] == null:
            timers[lastCreated] = CreateTimer()
            SaveInteger(TABLE, 0, GetHandleId(timers[lastCreated]), lastCreated)
        return lastCreated

    global TickDestroy(tick whichTick):
        PauseTimer(timers[whichTick])
        tickindexer.destroy(whichTick)

    global TickStart(tick whichTick, real timeout, boolean periodic, code callback):
        TimerStart(timers[whichTick], timeout, periodic, callback)

    global GetExpiredTick() -> tick:
        return LoadInteger(TABLE, 0, GetHandleId(GetExpiredTimer()))

```

```
import tick

content:
    
    tick *contentTick

    onInterval():
        BJDebugMsg("WOW! 0.50 seconds passed!")

    init:
        contentTick = TickCreate()
        TickStart(contentTick, 0.50, true, function onInterval)
```

## vJass Form

```
library tick initializer onInit
    globals
        private constant integer INITIAL_TICK_INSTANCES = 1000
        private constant hashtable TABLE = InitHashtable()
        private timer array timers
        private integer lastCreated
    endglobals
    private function VJPID807C1A54A604E29 takes nothing returns nothing
        local integer i = 1
        loop
            exitwhen i > INITIAL_TICK_INSTANCES
            set timers[i] = CreateTimer()
            call SaveInteger(TABLE, 0, GetHandleId(timers[i]), i)
            set i = i + 1
        endloop
    endfunction
    private struct tickindexer
    endstruct
    struct tick extends array
    endstruct
    function TickCreate takes nothing returns tick
        set lastCreated = tickindexer.create()
        if timers[lastCreated] == null then
            set timers[lastCreated] = CreateTimer()
            call SaveInteger(TABLE, 0, GetHandleId(timers[lastCreated]), lastCreated)
        endif
        return lastCreated
    endfunction
    function TickDestroy takes tick whichTick returns nothing
        call PauseTimer(timers[whichTick])
        call tickindexer.destroy(whichTick)
    endfunction
    function TickStart takes tick whichTick, real timeout, boolean periodic, code callback returns nothing
        call TimerStart(timers[whichTick], timeout, periodic, callback)
    endfunction
    function GetExpiredTick takes nothing returns tick
        return LoadInteger(TABLE, 0, GetHandleId(GetExpiredTimer()))
    endfunction
    private function onInit takes nothing returns nothing
        call VJPID807C1A54A604E29()
    endfunction
endlibrary
scope VJPS18F46CB218474831 initializer onInit
    globals
        private tick contentTick
    endglobals
    private function onInterval takes nothing returns nothing
        call BJDebugMsg("WOW! 0.50 seconds passed!")
    endfunction
    private function VJPIEE9374976E9E40A1 takes nothing returns nothing
        set contentTick = TickCreate()
        call TickStart(contentTick, 0.50, true, function onInterval)
    endfunction
    private function onInit takes nothing returns nothing
        call VJPIEE9374976E9E40A1()
    endfunction
endscope
```
