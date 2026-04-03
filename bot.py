import os
import discord
import matplotlib
matplotlib.use('Agg')
from dotenv import load_dotenv
from ai_mega_dungeon import AIMegaDungeon

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Define intents (necessary for modern bots)
intents = discord.Intents.default()
intents.message_content = True  # Enable the bot to read message content
client = discord.Client(intents=intents)

aimd = AIMegaDungeon(keys=os.getenv('AI_TOKENS'))

def get_numbers(my_string):
    numbers_only_str = ''
    for char in my_string:
        if char.isdigit():
            numbers_only_str += char
    if numbers_only_str != '':
        return int(numbers_only_str)
    else:
        return 0
        
@client.event
async def on_ready():
    """Triggered when the bot is connected to Discord."""
    print(f'{client.user} has connected to Discord!')

@client.event
async def on_message(message):
    """Triggered every time a message is sent in a channel."""
    if message.author == client.user:
        return # Prevents the bot from responding to itself

    if message.content.startswith('$hello'):
        await message.channel.send('Hi there!')
        return
    #### have it read messages and add functions
    #### Best to dev the dungeon out in a Jupyter Notebook, save it, and load it here.
    
    ## $load
    if message.content.startswith('$load'):
        syntax = '''SYNTAX:
        $load "[GameName]"
        '''
        try:
            content = message.content 
            gname = content.split(' "')[1].replace('"','')
        except:
            await message.channel.send(syntax)  
            return
        print(gname)
        aimd.load(filename=gname)
        print(aimd.dungeon_name)
        await message.channel.send('Loaded {}: {}'.format(gname,aimd.dungeon_name))
        lst = aimd.timekeeping()
        for b in lst:
                await message.channel.send(b)
        
        return
        
    ## $save
    if message.content.startswith('$save'):
        syntax = '''SYNTAX:
        $save "[GameName]" '''
        try:
            content = message.content 
            gname = content.split(' "')[1].replace('"','')
        except:
            await message.channel.send(syntax)  
            return
            
        aimd.save(filename=gname)
        await message.channel.send('{} Saved.'.format(gname))
        return
        
    # $quests     
    if message.content.startswith('$quests'):
        print(aimd.quests)
        quests = aimd.get_quests()
        print(quests)
        for quest in quests:
            print(quest)
            # Send an initial message
            qmessage = await message.channel.send('{}'.format(quest))
            qtitle = quest.split(' [')[0]
            
            # Create a thread from that message
            thread = await qmessage.create_thread(
                name=qtitle,
                auto_archive_duration=60 # Duration in minutes (60, 1440, etc.)
            )
            await thread.send(aimd.get_quest(qtitle, dm=True)[3])
        return
        
    # $timer
    if message.content.startswith('$timer'):
        syntax = '''
        Add a timer of [event] for time N
        $timer "event=[event]" ["hours=N"] ["seconds=N"] ["turns=N"] ["rnds=N"] ["minutes=N"] ["days=N"]
        '''
        content = message.content.split(' "')
        hours,s,days,mins,rnds,turns = 0,0,0,0,0,0
        try:
            event = content[1].split('=')[1].replace('"','')
            a = content[2]
        except:
            await message.channel.send(syntax)
            return
        for a in content[2:]:
            if 'h' in a:
                hours = get_numbers(a)
            elif 'seconds' in a.lower():
                seconds = get_numbers(a)
            elif 't' in a.lower():
                turns = get_numbers(a)
            elif 'r' in a.lower():
                rnds = get_numbers(a)
            elif 'm' in a.lower():
                mins = get_numbers(a)
            elif 'd' in a.lower():
                days = get_numbers(a)
            elif 's' in a.lower():
                s = get_numbers(a)
            else:
                await message.channel.send(syntax)
                return
            
        aimd.add_timer(event, hours, s, days, mins, rnds, turns)
        lst = aimd.timekeeping()
        for b in lst:
            await message.channel.send(b)      
        return
        
    # $time
    if message.content.startswith('$time'):
        syntax = '''SYNTAX:
        Get the current time
        $time
        
        OR
        Pass N amount of Time
        $time ["hours=N"] ["seconds=N"] ["turns=N"] ["rnds=N"] ["minutes=N"] ["days=N"]
        '''
        content = message.content
        hours,s,days,mins,rnds,turns = 0,0,0,0,0,0
        if len(content.split(' "')) > 1:
            for a in content.split(' '):
                if 'h' in a:
                    hours = get_numbers(a)
                elif 'seconds' in a:
                    seconds = get_numbers(a)
                elif 't' in a:
                    turns = get_numbers(a)
                elif 'r' in a:
                    rnds = get_numbers(a)
                elif 'm' in a:
                    mins = get_numbers(a)
                elif 'd' in a:
                    days = get_numbers(a)
                elif 's' in a:
                    s = get_numbers(a)
                else:
                    await message.channel.send(syntax)
                    return
        lst = aimd.pass_time(hours, s, days, mins, rnds, turns)
        for b in lst:
            await message.channel.send(b)
        return   
        
    #dm-bad-image
    if message.content.startswith('$dm-bad-image'):
        room = aimd.current_room
        try:
            image_location =  aimd.file_path("Rooms/{} Level {} Room {}.png".format(aimd.filename, room.parent.info['level'], room.room_id))
            os.remove(image_location)
        except FileNotFoundError:
            print('File not found')
        message.content='$explore'
        # no return, explore is next...
        
    # $explore
    if message.content.startswith('$explore') or message.content.startswith('$dm-explore'):
        content = message.content
        try:
            room, doors = aimd.explore(room=aimd.current_room)
        except:
            await message.channel.send('Entering the dungeon through the main enterance...')
            room, doors = aimd.explore()
        
        if content[:3]=='$dm':
           await message.channel.send('{} [{}]\n\n{}'.format(room.purpose,room.state,room.description))
        image_location =  aimd.file_path("Rooms/{} Level {} Room {}.png".format(aimd.filename, room.parent.info['level'], room.room_id))
        if len(room.blocks) >= 2:
            with open(image_location, 'rb') as f:
                picture = discord.File(f, filename=image_location)
                await message.channel.send(file=picture)
        if len(doors) >= 1:
            await message.channel.send('Exits:')
            for d in doors:
                await message.channel.send(d)
        return
        
    # $open
    if message.content.startswith('$open'):
        syntax = '''SYNTAX
        $open "[Door]" ["unlocked=True"]
        
        [Door] is as written in $explore response
        '''
        contents = message.content.split(' "')
        try:
            door_key = contents[1].replace('"','')
        except:
            await message.channel.send(syntax)
            return
        unlock = False
        if len(contents)>=3:
            unlocked = contents[2]
            if 'true' in unlocked.lower():
                unlock = True
            else:
                await message.channel.send(syntax)
                return
        reply = aimd.open_door(door_key = door_key, unlocked=unlock)
        await message.channel.send(reply)
        return
        
    # $dm-clear-room
    if message.content.startswith('$dm-clear-room'):
        syntax = '''SYNTAX
        $dm-clear-room --True
        
        Need the --True to make sure we really want to do this.
        Use $remove-furnishings to remove furnishings
        '''
        if '--True' in message.content:
            aimd.current_room.clear_room(clear_all = False)
            await message.channel.send('{} cleared'.format(aimd.current_room.room_id))
        else:
            await message.channel.send(syntax)
        return
        
    # $remove-furnishing
    if message.content.startswith('$remove-furnishing'):
        syntax = '''SYNTAX
        $remove-furnishing "[General Furnishishings: Object" ["Other: object"]
        
        Each must be written exactly as it appears in the list, there is one space after the colon.
        '''
        contents = message.content.split(' "')
        for item in contents:
            if '$remove-furnishing' not in item:
                try:
                    print(item[:-1])
                    a = aimd.current_room.furnishings.pop(aimd.current_room.furnishings.index(item[:-1]))
                    print(a)
                    await message.channel.send('{} Removed'.format(a))
                except ValueError as e:
                    await message.channel.send('{}\n\n{}'.format(e, syntax))
        return
                
    # $dm-npc
    if message.content.startswith('$dm-npc'):
        syntax = '''
        creates or returns an NPC.  Any details not specified are randomly generated
        
        $dm-npc "name=[Name]" 
                ["vitals=Race/Class/Occupation"] 
                ["appearance=None"] 
                ["abilities=High/Low ability scores"]
                ["talent=any special talents"]
                ["mannerisms=mannerism(s)"]
                ["personality=brief description or adjectives"]
                ["notes=any other notes"]
        '''
        contents = message.content.split(' "')
        vitals = None
        appearance = None 
        abilities = None
        talent = None
        mannerisms = None
        personality = None
        notes = None
        
        try:
            name = contents[1].split('=')[1].replace('"','')
        except:
            await message.channel.send(syntax)
            return
        for a in contents:
            b = a.split('=')
            if a == "$dm-npc" or a[:4].lower()=='name':
                print(a)
            elif b[0].lower() == 'vitals':
                vitals = b[1][:-1]
            elif b[0].lower() == 'appearance':
                appearance = b[1][:-1]
            elif b[0].lower() == 'abilities':
                abilities = b[1][:-1]
            elif b[0].lower() == 'talent':
                talent = b[1][:-1]
            elif b[0].lower() == 'mannerisms':
                mannerisms = b[1][:-1]   
            elif b[0].lower() == 'personality':
                personality = b[1][:-1]
            elif b[0].lower() == 'notes':
                notes = b[1][:-1]
            else:
                await message.channel.send(syntax)
                return
        npc = aimd.get_npc(name, vitals, appearance, abilities, talent, mannerisms, personality, notes)
        await message.channel.send(npc)
        return
        
        
# Run the bot with your token
client.run(TOKEN)
