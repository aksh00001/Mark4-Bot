import json

# TranslucentTB Control Functions
def get_translucenttb_config():
    """Read current TranslucentTB configuration"""
    try:
        with open(TRANSLUCENTTB_CONFIG, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log(f"TranslucentTB Config Read Error: {e}")
        return None

def set_translucenttb_config(config):
    """Write TranslucentTB configuration and restart the app"""
    try:
        with open(TRANSLUCENTTB_CONFIG, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        
        # Restart TranslucentTB to apply changes
        subprocess.call('taskkill /F /IM TranslucentTB.exe', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        time.sleep(0.5)
        subprocess.Popen(['explorer.exe', 'shell:AppsFolder\\28017CharlesMilette.TranslucentTB_v826wp6bftszj!App'], creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except Exception as e:
        log(f"TranslucentTB Config Write Error: {e}")
        return False

def set_taskbar_mode(mode='clear', color='#00000000', blur_radius=9.0):
    """
    Set taskbar appearance mode
    Modes: 'clear', 'acrylic', 'blur', 'opaque', 'normal'
    """
    config = get_translucenttb_config()
    if not config:
        return False
    
    config['desktop_appearance']['accent'] = mode
    config['desktop_appearance']['color'] = color
    config['desktop_appearance']['blur_radius'] = blur_radius
    
    return set_translucenttb_config(config)

# Command Handler
async def taskbar_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Control TranslucentTB taskbar appearance"""
    if not is_authorized(update.effective_user.id): return
    
    args = context.args
    if not args:
        await retry_send_message(update, 
            "🎨 **Taskbar Control**\\n\\n"
            "Usage: `/taskbar <mode> [color] [blur]`\\n\\n"
            "**Modes:**\\n"
            "• `clear` - Fully transparent\\n"
            "• `acrylic` - Frosted glass effect\\n"
            "• `blur` - Blurred background\\n"
            "• `opaque` - Solid color\\n"
            "• `normal` - Windows default\\n\\n"
            "**Examples:**\\n"
            "`/taskbar clear`\\n"
            "`/taskbar acrylic #1E1E1E80 12`\\n"
            "`/taskbar blur #00000040 15`",
            parse_mode='Markdown'
        )
        return
    
    mode = args[0].lower()
    color = args[1] if len(args) > 1 else '#00000000'
    blur_radius = float(args[2]) if len(args) > 2 else 9.0
    
    valid_modes = ['clear', 'acrylic', 'blur', 'opaque', 'normal']
    if mode not in valid_modes:
        await retry_send_message(update, f"❌ Invalid mode. Use: {', '.join(valid_modes)}")
        return
    
    status_msg = await retry_send_message(update, f"🎨 Applying `{mode}` mode...")
    
    if set_taskbar_mode(mode, color, blur_radius):
        await retry_send_message(update, f"✅ Taskbar set to **{mode.upper()}** mode. Blur: {blur_radius}")
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_msg.message_id)
        except: pass
    else:
        await retry_send_message(update, "❌ Failed to update taskbar settings.")
