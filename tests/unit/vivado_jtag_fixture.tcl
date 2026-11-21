# An intentionally small hardware model for exercising the batch dispatcher.
if {[llength [info commands exit]]} { rename exit real_exit }
proc exit {code} { if {$code != 0} { error "Batch failed" } }
set clock_hz 6000000
set opened 0
set requested_operation ""
proc open_hw_manager {} {}
proc close_hw_manager {} {}
proc connect_hw_server {flag url} {
    if {$url eq "127.0.0.1:3121" && [info exists ::env(FAKE_VIVADO_REFUSE_DEFAULT)] &&
        $::env(FAKE_VIVADO_REFUSE_DEFAULT) eq "true"} { error "wrong service" }
    return server
}
proc disconnect_hw_server {server} {}
proc current_hw_server {} { return server }
proc version {flag} { return 2025.2 }
proc get_hw_targets {args} {
    if {[info exists ::env(FAKE_VIVADO_TARGETS)]} { return {target target2} }
    return target
}
proc open_hw_target {args} { set ::opened 1 }
proc close_hw_target {target} { set ::opened 0 }
proc current_hw_target {} { return target }
proc get_hw_devices {args} {
    if {[info exists ::env(FAKE_VERSAL_DONE)] && $::env(FAKE_VERSAL_DONE) ne "missing_dap"} {
        return {chip arm_dap_0}
    }
    return chip
}
proc current_hw_device {args} { return chip }
proc list_property {object} {
    switch -- $object {
        target - target2 { return {UID NAME IS_OPENED PARAM.FREQUENCY} }
        chip { return {PART IDCODE REGISTER.IR.BIT5_DONE PROGRAM.HW_CFGMEM_BITFILE PROGRAM.HW_CFGMEM_TYPE} }
        arm_dap_0 { return {{REGISTER.JTAG_STATUS.BIT[34]_DONE}} }
        flash-a { return {NAME MEM_TYPE} }
        cfgmem { return {PROGRAM.FILES PROGRAM.ADDRESS_RANGE PROGRAM.ZYNQ_FSBL} }
    }
    return {}
}
proc get_property {name object} {
    switch -- $name {
        UID { return [expr {$object eq "target" ? "cable-1" : "cable-2"}] }
        NAME { return [expr {$object eq "target" ? "test-target" : $object}] }
        IS_OPENED { return $::opened }
        PARAM.FREQUENCY { return $::clock_hz }
        PART {
            if {[info exists ::env(FAKE_VIVADO_PART)]} { return $::env(FAKE_VIVADO_PART) }
            return xc7a35t
        }
        IDCODE { return 0362D093 }
        REGISTER.IR.BIT5_DONE { return 1 }
        {REGISTER.JTAG_STATUS.BIT[34]_DONE} {
            if {![info exists ::refreshed] || $::refreshed ne $object} { error "Status device was not refreshed" }
            return $::env(FAKE_VERSAL_DONE)
        }
        PROGRAM.HW_CFGMEM_BITFILE { return helper.bit }
        PROGRAM.HW_CFGMEM_TYPE { return none }
        MEM_TYPE { return spi }
    }
}
proc set_property {name value object} {
    set ::props($object,$name) $value
    if {$name eq "PARAM.FREQUENCY"} { set ::clock_hz $value }
}
proc run_state_hw_jtag {state} { return $state }
proc scan_ir_hw_jtag {flag tdi bits} { return 01 }
proc scan_dr_hw_jtag {flag tdi bits} { return 0362D093 }
proc program_hw_devices {device} {
    if {![info exists ::props($device,PROGRAM.FILE)] && ![info exists ::helper]} {
        error "No input image"
    }
}
proc refresh_hw_device {device} { set ::refreshed $device }
proc boot_hw_device {flag seconds device} { return 1 }
proc get_cfgmem_parts {} { return flash-a }
proc create_hw_cfgmem {flag device part} { return cfgmem }
proc create_hw_bitstream {flag device file} { set ::helper $file }
proc program_hw_cfgmem {cfg} {
    if {$::props($cfg,PROGRAM.VERIFY) != 1 ||
        $::props($cfg,PROGRAM.ERASE) != $::props($cfg,PROGRAM.CFG_PROGRAM)} {
        error "Unexpected flash flags"
    }
}
