from TTS.api import TTS
from UnlimitedGPT import ChatGPT
import discord
import functools
import typing
import asyncio
import json

# Load credentials from JSON file
with open("credentials.json", "r") as f:
    credentials = json.load(f)

# Initialize TTS and GPT models
tts = TTS(
    model_name='tts_models/en/jenny/jenny')  # tts_models/de/thorsten/vits #tts_models/multilingual/multi-dataset/bark #tts_models/de/thorsten/tacotron2-DDC
tts.to("cuda")

session_token = credentials["session_token"]
print(session_token)
discord_token = credentials["discord_token"]

api = ChatGPT(session_token=session_token, headless=False, chrome_args=['--no-sandbox'])

# Define a decorator to run a function in a separate thread
def to_thread(func: typing.Callable):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)

    return wrapper

# Define a function to generate TTS audio from a given prompt
@to_thread
def create_text(prompt: str):
    response = api.send_message(input_mode="SLOW", message=prompt)
    print("creating voice")
    tts.tts_to_file(text=response.response, speed=1, file_path="./sounds/output.wav")
    return response.response

# Define the main function to start the story
async def start(text_channel, voice_channel, author, theme):
    # Connect to the voice channel
    voice = await voice_channel.connect()
    # Generate a welcome message
    tts.tts_to_file(
        text=f"Welcome! Thank you {author}, for messaging me. Today, I want to tell you a story about {theme}",
        file_path="./sounds/output.wav", )
    audio_source = discord.FFmpegPCMAudio('./sounds/output.wav')
    voice.play(audio_source)
    # Generate the introduction message
    response = await create_text(f"You are a narrator for a story that is only told through text. "
                                 f"But you only tell a small part of the story, and the user has to "
                                 f"ask questions to find out more. And the user is the protagonist "
                                 f"and can decide what to do. You start with a small snippet "
                                 f"as an introduction. Use a lot of adjectives to create "
                                 f"atmosphere. Do not use the words 'user' and 'protagonist'. "
                                 f"Do not use markdown. Write in English. The topic is: {theme}  "
                                 f"and always address the user with you and tell the story as "
                                 f"if he is the protagonist, with the name {author}.")
    await text_channel.send(response)
    intro = discord.FFmpegPCMAudio('./sounds/output.wav')
    voice.play(intro)

    while True:
        try:
            # Wait for a message from the user
            msg = await bot.wait_for('message', timeout=300.0)
            while msg.channel != text_channel:
                msg = await bot.wait_for('message', timeout=300.0)
            if msg.content == "exit":
                raise asyncio.TimeoutError
        except asyncio.TimeoutError:
            # If there is no message for 5 minutes, end the story
            await text_channel.send("Goodbye, see you next time.")
            await voice.disconnect()
            api.reset_conversation()
            return
        print(msg.content)
        # Generate a sound to indicate that the bot is processing the message
        generate_sound = discord.FFmpegPCMAudio('./sounds/on.wav')
        voice.play(generate_sound)
        # Generate a response to the user's message
        response = await create_text(msg.content)
        await text_channel.send(response)
        audio = discord.FFmpegPCMAudio('./sounds/output.wav')
        voice.play(audio)

# Initialize the Discord bot
intents = discord.Intents.all()
bot = discord.Bot(intents=intents)

# Define a command to start a new story
@bot.command(name="storytime", description="Starts a new story")
async def on_message(ctx, theme: discord.Option(str, description="The theme of the story", required=False)):
    try:
        print(ctx.user.voice.channel)
    except AttributeError:
        await ctx.respond("You must be in a voice channel to start a story.", ephemeral=True)
        return
    await ctx.respond("I'll start a story shortly. Please wait a moment.", ephemeral=True)
    if theme is None:
        # If no theme is provided, generate one with ChatGPT
        response = api.send_message(
            "Complete the sentence briefly with an idea for an exciting story: The story is about")
        theme = response.response.replace("The story is about ", "")
        short_theme = (api.send_message("Summarize the sentence in MAXIMUM 50 characters")
                       .response
                       .replace("""""""", ""))
        print(len(short_theme))
        api.reset_conversation()
    else:
        # If a theme is provided, summarize it in 50 characters or less
        short_theme = api.send_message(f"Summarize the sentence in MAXIMUM 50 characters: {theme}").response.replace(
            """""""", "")
        api.reset_conversation()

    channel = ctx.channel
    author = str(ctx.author)
    author = author.split("#")[0]
    await ctx.respond("Creating a story about " + author + " with the theme: " + short_theme)

    try:
        # Create a new thread for the story
        thread = await channel.create_thread(name=short_theme, type=discord.ChannelType.public_thread)
    except discord.errors.HTTPException:
        await ctx.respond("There was a problem creating the thread. Please try again.")
        return

    print("Starting telling: " + str(channel), theme, author, thread, ctx.user.voice.channel)
    await start(thread, ctx.user.voice.channel, author, theme)

# Run the bot
bot.run(discord_token)
