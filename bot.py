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
        content = message.content 
        aimd.load(filename=content.split(' ')[1])
        print(aimd.dungeon_name)
        await message.channel.send('Loaded {}: {}'.format(content.split(' ')[1],aimd.dungeon_name))
        lst = aimd.timekeeping()
        for b in lst:
            await message.channel.send(b)
        return
        
    ## $save
    if message.content.startswith('$save'):
        content = message.content 
        aimd.save(filename=content.split(' ')[1])
        await message.channel.send('Saved {}: {}'.format(content.split(' ')[1],aimd.dungeon_name))
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
        content = message.content.split('"')
        hours,s,days,mins,rnds,turns = 0,0,0,0,0,0
        event = content[1]
        a = content[2] 
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
        aimd.add_timer(event, hours, s, days, mins, rnds, turns)
        lst = aimd.timekeeping()
        for b in lst:
            await message.channel.send(b)      
        return
        
    # $time
    if message.content.startswith('$time'):
        content = message.content
        hours,s,days,mins,rnds,turns = 0,0,0,0,0,0
        if len(content.split(' ')) > 1:
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
        lst = aimd.pass_time(hours, s, days, mins, rnds, turns)
        for b in lst:
            await message.channel.send(b)
        return   
        
    #dm-bad-image
    if message.content.startswith('$dm-bad-image'):
        room = aimd.current_room
        image_location =  aimd.file_path("Rooms/{} Level {} Room {}.png".format(aimd.filename, room.parent.info['level'], room.room_id))
        os.remove(image_location)
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
        contents = message.content.split(' ')
        door_key = contents[1]
        unlock = False
        if len(contents)>=3:
            unlocked = contents[2]
            if 'true' in unlcoked.lower():
                unlock = True
        reply = aimd.open_door(door_key = door_key, unlocked=unlock)
        await message.channel.send(reply)
        return
        
# Run the bot with your token
client.run(TOKEN)
