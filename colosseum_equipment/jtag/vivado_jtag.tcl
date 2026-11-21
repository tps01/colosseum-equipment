# Vivado batch entry point. Request and result files use tab-separated base64 fields.
namespace eval ::colosseum_jtag {
    variable request {}
    variable result
    variable server ""
    variable opened ""
    variable phase startup
}

proc ::colosseum_jtag::load_request {} {
    variable request
    set file [open request r]
    try {
        foreach line [split [read $file] "\n"] {
            if {$line eq ""} { continue }
            lassign [split $line "\t"] field value
            dict lappend request $field [encoding convertfrom utf-8 [binary decode base64 $value]]
        }
    } finally {
        close $file
    }
}

proc ::colosseum_jtag::arg {name {default ""}} {
    variable request
    if {[dict exists $request $name]} { return [lindex [dict get $request $name] 0] }
    return $default
}

proc ::colosseum_jtag::values {name} {
    variable request
    if {[dict exists $request $name]} { return [dict get $request $name] }
    return {}
}

proc ::colosseum_jtag::emit {tag args} {
    variable result
    set row [list $tag]
    foreach value $args {
        lappend row [binary encode base64 -maxlen 0 [encoding convertto utf-8 $value]]
    }
    puts $result [join $row "\t"]
    flush $result
}

proc ::colosseum_jtag::capability {message} {
    return -code error -errorcode {COLOSSEUM CAPABILITY} $message
}

proc ::colosseum_jtag::property {name object} {
    if {$name in [list_property $object]} { return [get_property $name $object] }
    return ""
}

proc ::colosseum_jtag::choose {label objects selector properties} {
    set choices {}
    set matches {}
    foreach item $objects {
        set ids [list $item]
        foreach name $properties {
            set id [property $name $item]
            if {$id ne ""} { lappend ids $id }
        }
        lappend choices $ids
        if {$selector eq "" || $selector in $ids} { lappend matches $item }
    }
    if {[llength $matches] != 1} {
        error "Select exactly one $label (requested '$selector'); available: $choices"
    }
    return [lindex $matches 0]
}

proc ::colosseum_jtag::target_row {target} {
    set uid [property UID $target]
    if {$uid eq ""} { set uid $target }
    emit target_row $uid [property NAME $target]
}

proc ::colosseum_jtag::open_target {raw} {
    variable server
    variable opened
    variable phase
    set phase target
    set selector [arg target]
    set xvc [arg xvc_url]
    set clock [arg clock_hz]
    set flags {}
    if {$raw} { lappend flags -jtag_mode on }
    if {$xvc ne ""} {
        open_hw_target {*}$flags -xvc_url $xvc
        set opened [current_hw_target]
        choose target [list $opened] $selector {UID NAME}
        if {$clock ne ""} {
            set target $opened
            close_hw_target $target
            set opened ""
            if {[catch {set_property PARAM.FREQUENCY $clock $target} detail]} {
                capability "XVC target cannot apply $clock Hz: $detail"
            }
            open_hw_target {*}$flags $target
            set opened [current_hw_target]
        }
    } else {
        set target [choose target [get_hw_targets -of_objects $server] $selector {UID NAME}]
        if {$clock ne "" && [catch {set_property PARAM.FREQUENCY $clock $target} detail]} {
            capability "Target cannot apply $clock Hz: $detail"
        }
        open_hw_target {*}$flags $target
        set opened [current_hw_target]
    }
    if {$opened eq "" || ![property IS_OPENED $opened]} { error "Hardware target did not open" }
    target_row $opened
    emit requested_clock_hz $clock
    set applied [property PARAM.FREQUENCY $opened]
    set rate ""
    if {[string is double -strict $applied] && $applied > 0} { set rate [expr {round($applied)}] }
    emit clock_hz $rate
    emit clock_scope batch
    if {$clock ne "" && $rate eq ""} { capability "Target did not report an applied JTAG clock" }
    if {$clock ne "" && $rate != $clock} { emit clock_adjusted true }
    return $opened
}

proc ::colosseum_jtag::family {device} {
    set part [string tolower [property PART $device]]
    if {[regexp {^(xc|xa|xq)7z} $part]} { return zynq }
    if {[regexp {^(xc|xa|xq)zu} $part]} { return zynq }
    if {[regexp {^(xc|xa|xq)(v[cemph]|2v)} $part]} { return versal }
    if {[regexp {^(xc|xa|xq)(7[a-z]|[akvs]u)} $part]} { return fpga }
    capability "No built-in hardware flow for part '$part'"
}

proc ::colosseum_jtag::configured {device} {
    foreach name {REGISTER.IR.BIT5_DONE REGISTER.CONFIG_STATUS.BIT14_DONE_PIN {REGISTER.JTAG_STATUS.BIT[34]_DONE}} {
        set value [property $name $device]
        if {[string is boolean -strict $value]} { return [expr {$value ? 1 : 0}] }
    }
    return ""
}

proc ::colosseum_jtag::versal_status_device {device devices} {
    # Vivado exposes Versal DONE on the following arm_dap in the hardware chain.
    set companion [lindex $devices [expr {[lsearch -exact $devices $device] + 1}]]
    if {$companion ne ""} {
        foreach name [list $companion [property NAME $companion] [property PART $companion]] {
            if {[regexp -nocase {^arm_dap(_[0-9]+)?$} $name]} { return $companion }
        }
    }
    capability "No companion arm_dap found after selected Versal device '$device'"
}

proc ::colosseum_jtag::do_scan {} {
    foreach step [values steps] {
        lassign $step kind bits tdi
        switch -- $kind {
            IR { set tdo [scan_ir_hw_jtag -tdi $tdi $bits] }
            DR { set tdo [scan_dr_hw_jtag -tdi $tdi $bits] }
            default { run_state_hw_jtag $kind; continue }
        }
        emit scan_row $kind $bits $tdo
    }
}

proc ::colosseum_jtag::do_flash {device family verify} {
    set image [arg image]
    set ext [string tolower [file extension $image]]
    set init [arg initialization_pdi]
    set fsbl [arg fsbl]
    if {$family eq "versal"} {
        if {$ext ne ".pdi" || $init eq "" || $fsbl ne ""} {
            error "Versal needs a boot PDI and an initialization PDI"
        }
    } elseif {$ext ni {.mcs .bin} || $init ne "" || ($family ne "zynq" && $fsbl ne "")} {
        error "Supply .mcs or .bin and family-appropriate helper artifacts"
    }

    set part [choose flash_part [get_cfgmem_parts] [arg flash_part] {NAME}]
    set cfg [create_hw_cfgmem -hw_device $device $part]
    if {$cfg eq ""} { set cfg [get_property PROGRAM.HW_CFGMEM $device] }
    if {$family eq "versal"} {
        # Use the writable initialization-PDI property exported by this build.
        # Refuse writes when the native flow cannot be identified unambiguously.
        set props [lsearch -all -inline -regexp [list_property $cfg] {^PROGRAM\..*(INIT.*PDI|PDI.*INIT)}]
        if {[llength $props] != 1} {
            capability "Cannot identify the Versal initialization PDI property on this Vivado/device"
        }
        set_property [lindex $props 0] $init $cfg
    }
    if {$fsbl ne ""} { set_property PROGRAM.ZYNQ_FSBL $fsbl $cfg }
    if {"PROGRAM.FILES" in [list_property $cfg]} {
        set_property PROGRAM.FILES [list $image] $cfg
    } else {
        set_property PROGRAM.FILE $image $cfg
    }
    set_property PROGRAM.ADDRESS_RANGE use_file $cfg
    set_property PROGRAM.ERASE [expr {!$verify}] $cfg
    set_property PROGRAM.BLANK_CHECK 0 $cfg
    set_property PROGRAM.CFG_PROGRAM [expr {!$verify}] $cfg
    set_property PROGRAM.VERIFY 1 $cfg
    if {$family ne "versal"} {
        set helper [property PROGRAM.HW_CFGMEM_BITFILE $device]
        set current [property PROGRAM.HW_CFGMEM_TYPE $device]
        set requested [property MEM_TYPE $part]
        if {$helper ne "" && ($requested eq "" || $current ne $requested)} {
            create_hw_bitstream -hw_device $device $helper
            program_hw_devices $device
            emit temporary_device_configuration true
        }
    }
    program_hw_cfgmem $cfg
    emit flash_part [arg flash_part]
    emit image $image
    emit flash_verified true
    emit flash_written [expr {!$verify}]
}

proc ::colosseum_jtag::dispatch {} {
    variable phase
    variable server
    variable opened
    set operation [arg operation]
    set phase server
    open_hw_manager
    connect_hw_server -url [arg hw_server_url]
    set server [current_hw_server]
    if {[llength $server] != 1} { error "Expected a single hardware server connection" }
    close [open server-ready w]
    emit vivado_version [version -short]
    if {$operation eq "list_cfgmem_parts"} {
        foreach part [get_cfgmem_parts] { emit part_row $part }
        return
    }
    if {$operation eq "list_targets" && [arg xvc_url] eq ""} {
        foreach target [get_hw_targets -of_objects $server] { target_row $target }
        return
    }
    set target [open_target [expr {$operation eq "scan"}]]
    set phase $operation
    switch -- $operation {
        list_targets - get_clock - set_clock { return }
        scan { do_scan; return }
    }
    set devices [get_hw_devices -of_objects $target]
    if {$operation eq "list_devices"} {
        foreach device $devices {
            emit device_row $device [property PART $device] [property IDCODE $device]
        }
        return
    }
    set device ""
    if {$operation ne "run_tcl" || [arg device] ne ""} {
        set device [choose device $devices [arg device] {NAME}]
        current_hw_device $device
        emit device $device
        emit part [property PART $device]
        emit idcode [property IDCODE $device]
    }
    if {$operation eq "run_tcl"} {
        set ::argv [values args]
        set ::argc [llength $::argv]
        set ::argv0 [arg script]
        if {$::argv0 ne ""} {
            set value [uplevel #0 [list source $::argv0]]
        } else {
            set value [uplevel #0 [arg tcl]]
        }
        emit tcl_result $value
        return
    }

    set family [family $device]
    emit family $family
    switch -- $operation {
        program_device {
            set image [arg image]
            set ext [string tolower [file extension $image]]
            if {($family eq "versal" && $ext ne ".pdi") || ($family ne "versal" && $ext ne ".bit")} {
                error "Image type does not match the selected device family"
            }
            set status_device $device
            if {$family eq "versal"} {
                set status_device [versal_status_device $device $devices]
            }
            set_property PROGRAM.FILE $image $device
            program_hw_devices $device
            refresh_hw_device $status_device
            if {$family eq "versal"} {
                set done [property {REGISTER.JTAG_STATUS.BIT[34]_DONE} $status_device]
                if {![string is boolean -strict $done]} {
                    error "Versal configuration completion could not be read from '$status_device'"
                }
                set done [expr {$done ? 1 : 0}]
            } else {
                set done [configured $status_device]
            }
            if {$done eq "0"} { error "Device did not report configuration complete" }
            emit configured $done
            emit image $image
        }
        program_cfgmem { do_flash $device $family 0 }
        verify_cfgmem { do_flash $device $family 1 }
        boot_probe { return }
        boot {
            if {$family ne "fpga"} { capability "This device requires board reset and boot evidence callbacks" }
            if {[configured $device] eq ""} { capability "Configuration completion is unavailable for $device" }
            set deadline [expr {[clock milliseconds] + [arg boot_ms]}]
            set boot_s [expr {max(1, int(ceil([arg boot_ms] / 1000.0)))}]
            if {[boot_hw_device -timeout $boot_s $device] eq "0"} {
                emit configured false
                emit boot_method soft_boot
                return
            }
            while {[clock milliseconds] < $deadline} {
                refresh_hw_device $device
                if {[configured $device] eq "1" && [clock milliseconds] < $deadline} {
                    emit configured true
                    emit boot_method soft_boot
                    return
                }
                after 100
            }
            emit configured false
            emit boot_method soft_boot
        }
        default { error "Unknown operation '$operation'" }
    }
}

proc ::colosseum_jtag::main {} {
    variable result
    variable server
    variable opened
    variable phase
    set result [open result w]
    set failed [catch {load_request; dispatch} detail opts]
    if {$failed} {
        emit phase $phase
        emit error $detail
        if {[dict get $opts -errorcode] eq {COLOSSEUM CAPABILITY}} { emit kind capability }
        puts stderr [dict get $opts -errorinfo]
    }
    # Publish the operation result before any hardware cleanup can block.
    emit complete
    close $result
    if {$opened ne ""} { catch {close_hw_target $opened} }
    if {$server ne ""} { catch {disconnect_hw_server $server} }
    catch {close_hw_manager}
    exit $failed
}

::colosseum_jtag::main
