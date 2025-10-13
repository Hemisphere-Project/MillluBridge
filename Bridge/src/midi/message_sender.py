def send_midi_message(midi_out, midi_message):
    """
    Send a MIDI message through the given MIDI output
    
    Args:
        midi_out: rtmidi.MidiOut instance
        midi_message: List of MIDI bytes, e.g. [144, 60, 100] for Note On
    """
    try:
        if midi_out and isinstance(midi_message, (list, tuple)):
            midi_out.send_message(midi_message)
            print(f"Sent MIDI message: {midi_message}")
    except Exception as e:
        print(f"Error sending MIDI message: {e}")