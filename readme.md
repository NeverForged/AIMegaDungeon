\# AIMegaDungeon



\## \*An Appendix A Randomized Dungeon Maker\*



\### THE UNDERWORLD



\#### From \*VOLUME 3: THE UNDERWORLD \& WILDERNESS ADVENTURES\* BY GARY GYGAX \& DAVE ARNESON



Before it is possible to conduct a campaign of adventures in the mazey dungeons, it is necessary for the referee to sit down with pencil in hand and draw these labyrinths on graph paper. Unquestionably this will require a great deal of time and effort and imagination. The dungeons should look something like the example given below, with numerous levels which sprawl in all directions, not necessarily stack neatly above each other in a straight line.



In beginning a dungeon it is advisable to construct at least three levels at once, noting where stairs, trap doors (and chimneys) and slanting passages come on lower levels, as well as the mouths of chutes and teleportation terminals. In doing the lowest level of such a set it is also necessary to leave space for the various methods of egress to still lower levels. \*\*A good dungeon will have no less than a dozen levels down, with offshoot levels in addition, and new levels under construction so that players will never grow tired of it.\*\* There is no real limit to the number of levels, nor is there any restriction on their size (other than the size of graph paper available). "Greyhawk Castle", for example, has over a dozen levels in succession downwards, more than that number branching from these, and not less than two new levels under construction at any given time. These levels contain such things as a museum from another age, an underground lake, a series of caverns filled with giant fungi, a bowling alley for 20' high Giants, an arena of evil, crypts, and so on.



\## This Code



\- Based loosely on https://tiendil.org/en/posts/dungeon-generation-from-simple-to-complex

\- Uses a slightly modified version of Appendix A

&#x20; - Stairs are all spiral, and only go up or down 1 level

&#x20; - Every exit from a room is a door, for ease of coding

&#x20; - Passages are randomized in length

\- Appendix A is used to 'stock' the dungeon, with AI used to write encounters and roll on treasure tables (copying the DMG treasure and magic item tables is tedious)

&#x20; - Encounters are supplied with 3 rounds of enemy strategy, to make this as headless-friendly as possible

&#x20; - CR of encounters is randomized to be 1d3+1 per level away from the first level. This makes things harder as you go down, but allows you to start at level 1 and have fun.

\- Rooms can be rendered using AI Art to create cinematic, walls-visible room layouts for battle maps or narrational use.

\- NetworkX was used so that pathing may be calculated for spells/tracking

\- A datetime system is in place to track time, as Gygax said "YOU CAN NOT HAVE A MEANINGFUL CAMPAIGN IF STRICT TIME RECORDS ARE NOT KEPT"

&#x20; - The system allows timers to be stored and updated

&#x20; - Based on Unix time -670 years, +180 days... (or can be set)

&#x20; - Uses a real world calendar, but a fantasy calendar could be implemented

\- Discord: `bot.py` is an attempt to make a Discord Bot that loads the Dungeon and interacts with it, with various commands to allow a playstyle of switching DMs.

\- `AIgaDungeon.js` is an API MOD for Roll20 that this code can interact with and edit the current room for new rooms you travel to, and puts the encounter script in a handout under GMNotes.

