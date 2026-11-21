# Runs under quartus_stp. The request uses tab-separated UTF-8 fields encoded as hex.
namespace eval ::colosseum_jtag {
    variable request {}
}

proc ::colosseum_jtag::values {key} {
    variable request
    if {[dict exists $request $key]} { return [dict get $request $key] }
    return {}
}

proc ::colosseum_jtag::arg {key} { return [lindex [values $key] 0] }

proc ::colosseum_jtag::load_request {} {
    variable request
    set file [open request r]
    set data [read $file]
    close $file
    foreach line [split $data "\n"] {
        if {$line eq ""} { continue }
        lassign [split $line "\t"] key value
        dict lappend request $key [encoding convertfrom utf-8 [binary format H* $value]]
    }
}

proc ::colosseum_jtag::scan_steps {stream} {
    foreach step [values steps] {
        lassign $step kind bits tdi
        switch -- $kind {
            IDLE { device_run_test_idle }
            IR { puts $stream [format %X [device_ir_shift -ir_value 0x$tdi]] }
            DR { puts $stream [device_dr_shift -length $bits -dr_value $tdi -value_in_hex] }
        }
    }
}

proc ::colosseum_jtag::scan {stream} {
    open_device -hardware_name $::jtag_target -device_name $::jtag_device
    set status [catch {
        device_lock -timeout [arg lock_ms]
        set shift_status [catch {scan_steps $stream} shift_message shift_options]
        set unlock_status [catch {device_unlock} unlock_message unlock_options]
        if {$shift_status} { return -options $shift_options $shift_message }
        if {$unlock_status} { return -options $unlock_options $unlock_message }
    } message options]
    set close_status [catch {close_device} close_message close_options]
    if {$status} { return -options $options $message }
    if {$close_status} { return -options $close_options $close_message }
}

proc ::colosseum_jtag::dispatch {} {
    load_request
    set ::jtag_target [arg target]
    if {$::jtag_target ni [get_hardware_names]} { error "Selected Quartus cable disappeared" }
    set ::jtag_device ""
    if {[arg device] ne ""} {
        set matches {}
        foreach name [get_device_names -hardware_name $::jtag_target] {
            if {[regexp {^(@[0-9]+):} $name -> position] && $position eq [arg device]} {
                lappend matches $name
            }
        }
        if {[llength $matches] != 1} { error "Selected Quartus JTAG device disappeared or is ambiguous" }
        set ::jtag_device [lindex $matches 0]
    }
    set stream [open result w]
    if {[arg operation] eq "scan"} {
        scan $stream
    } else {
        set ::argv [values args]
        set ::argc [llength $::argv]
        set ::argv0 [arg script]
        if {$::argv0 ne ""} {
            set value [uplevel #0 [list source $::argv0]]
        } else {
            set value [uplevel #0 [arg tcl]]
        }
        binary scan [encoding convertto utf-8 $value] H* encoded
        puts $stream $encoded
    }
    puts $stream complete
    close $stream
}

if {[catch {::colosseum_jtag::dispatch} detail options]} {
    puts stderr [dict get $options -errorinfo]
    exit 1
}
