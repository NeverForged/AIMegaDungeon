\# AIMegaDungeon

\## \_An Appendix A Randomized Dungeon Maker\_



\### THE UNDERWORLD

\#### From \_\*VOLUME 3:\* THE UNDERWORLD \& WILDERNESS ADVENTURES\_ BY GARY GYGAX \& DAVE ARNESON

Before it is possible to conduct a campaign of adventures in the mazey dungeons, it is necessary for the referee to sit down with pencil in hand and draw these is necessary of the terere to sit down w t dealo labyrinths on graph paper. Unquestionably this will require a great deal of time and effort and imagination. The dungeons should look something like the ex- and offortae chould ample given below, with numerous levels which sprawl in all directions, not necessarily stack neatly above each other in a straight line.



In beginning a dungeon it is advisable to construct at least three levels at once, noting where stairs, trap doors (and chimneys) and slanting passages come on lower levels, as well as the mouths of chutes and teleportation teterminals. In doing the lowest level of such a set it is also necessary to leave space for the th various methods of egress to still lower levels. \*\*A good dungeon geon will have no less than a dozen levels down, with offshoot levels in addition, and new levels under construction so that players will never grow tired of it.\*\* There is no real limit to the struction so that players will never grow tired of it. There is ho real limit to the number of levels, nor is there any restriction on their size (other than the size of o s tn size etits7e graph paper available). "Greyhawk Castle", for example, has over a dozen levels in succession downwards, more than that number branching from these, and not inn donr thats less than two new levels under construction at any given time. These levels contain such things as a museum from another age, age, ana underground lake, aa sseries of caverns filled with giant fungi, a bowling alley for 20' high Giants, an arena of evil, crypts, and so on.



\## This Code

\- Based loosely on https://tiendil.org/en/posts/dungeon-generation-from-simple-to-complex

\- Uses a slightly modified version of Appendix A

-- Stairs are all spiral, and only go up or down 1 level

-- every exit from a room is a door, for ease of coding

-- passages are randomized in length

\- Appendix A is used to 'stock' the dungeon, with AI used to write encounters and roll on treasure tables (copying the DMG treasure and magic item tables is tedious)

-- Encounters are supplied with 3 rounds of enemy strategy, to make this as headless-friendly as possible

-- CR of encounters is randomized to be 1d3+1 per level away from the first level.  This makes things harder as you go down, but allows you to start at level 1 and have fun.

\- Rooms can be rendered using AI Art to create cinematic, walls-visible room layouts for battle maps or narrational use.

\- NetworkX was used so that pathing may be calculated for spells/tracking

\- A datetime system is in place to track time, as Gygax said "YOU CAN NOT HAVE A MEANINGFUL CAMPAIGN IF STRICT TIME RECORDS ARE NOT KEPT"

-- The system allows timers to be stored and updated

-- based on Unix time -670 years, +180 days... (or can be set)

-- uses a real world calendar, but a fantasy calendar could be implemented

