import asyncio
import logging
import random
import textwrap

from d20 import roll
from discord.ext import commands

from cogs5e.models import embeds
from cogs5e.models.embeds import EmbedWithAuthor
from cogs5e.models.errors import InvalidArgument
from gamedata.compendium import compendium
from gamedata.lookuputils import available
from utils.functions import ABILITY_MAP, get_selection, search_and_select

log = logging.getLogger(__name__)

SKILL_MAP = {'acrobatics': 'acrobatics', 'animal handling': 'animalHandling', 'arcana': 'arcana',
             'athletics': 'athletics', 'deception': 'deception', 'history': 'history', 'initiative': 'initiative',
             'insight': 'insight', 'intimidation': 'intimidation', 'investigation': 'investigation',
             'medicine': 'medicine', 'nature': 'nature', 'perception': 'perception', 'performance': 'performance',
             'persuasion': 'persuasion', 'religion': 'religion', 'sleight of hand': 'sleightOfHand',
             'stealth': 'stealth', 'survival': 'survival'}

CLASS_RESOURCE_NAMES = {"Ki Points": "ki", "Rage Damage": "rageDamage", "Rages": "rages",
                        "Sorcery Points": "sorceryPoints", "Superiority Dice": "superiorityDice",
                        "1st": "level1SpellSlots", "2nd": "level2SpellSlots", "3rd": "level3SpellSlots",
                        "4th": "level4SpellSlots", "5th": "level5SpellSlots", "6th": "level6SpellSlots",
                        "7th": "level7SpellSlots", "8th": "level8SpellSlots", "9th": "level9SpellSlots"}


class CharGenerator(commands.Cog):
    """Random character generator."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='randchar')
    async def randchar(self, ctx, level=None):
        """Rolls up a random 5e character."""
        if level is None:
            rolls = [roll("4d6kh3") for _ in range(6)]
            stats = '\n'.join(str(r) for r in rolls)
            total = sum([r.total for r in rolls])
            await ctx.send(f"{ctx.message.author.mention}\nGenerated random stats:\n{stats}\nTotal = `{total}`")
            return

        try:
            level = int(level)
        except:
            await ctx.send("Invalid level.")
            return

        if level > 20 or level < 1:
            await ctx.send("Invalid level (must be 1-20).")
            return

        await self.send_character_details(ctx, level)

    @commands.command(aliases=['name'])
    async def randname(self, ctx, race=None, option=None):
        """Generates a random name, optionally from a given race."""
        if race is None:
            return await ctx.send(f"Your random name: {self.old_name_gen()}")

        embed = EmbedWithAuthor(ctx)
        race_names = await search_and_select(ctx, compendium.names, race, lambda e: e['race'])
        if option is None:
            table = await get_selection(ctx, [(t['name'], t) for t in race_names['tables']])
        else:
            table = await search_and_select(ctx, race_names['tables'], option, lambda e: e['name'])
        embed.title = f"{table['name']} {race_names['race']} Name"
        embed.description = random.choice(table['choices'])
        await ctx.send(embed=embed)

    @commands.command(name='charref')
    async def charref(self, ctx, level):
        """Gives you reference stats for a 5e character."""
        try:
            level = int(level)
        except:
            await ctx.send("Invalid level.")
            return
        if level > 20 or level < 1:
            await ctx.send("Invalid level (must be 1-20).")
            return

        race, _class, subclass, background = await self.select_details(ctx)

        await self.send_character_details(ctx, level, race, _class, subclass, background)

    async def select_details(self, ctx):
        author = ctx.author
        channel = ctx.channel

        def chk(m):
            return m.author == author and m.channel == channel

        await ctx.send(author.mention + " What race?")
        try:
            race_response = await self.bot.wait_for('message', timeout=90, check=chk)
        except asyncio.TimeoutError:
            raise InvalidArgument("Timed out waiting for race.")
        race_choices = await available(ctx, compendium.races, 'race')
        race = await search_and_select(ctx, race_choices, race_response.content, lambda e: e.name)

        await ctx.send(author.mention + " What class?")
        try:
            class_response = await self.bot.wait_for('message', timeout=90, check=chk)
        except asyncio.TimeoutError:
            raise InvalidArgument("Timed out waiting for class.")
        class_choices = await available(ctx, compendium.classes, 'class')
        _class = await search_and_select(ctx, class_choices, class_response.content, lambda e: e.name)

        subclass_choices = await available(ctx, _class.subclasses, 'subclass')
        if subclass_choices:
            await ctx.send(author.mention + " What subclass?")
            try:
                subclass_response = await self.bot.wait_for('message', timeout=90, check=chk)
            except asyncio.TimeoutError:
                raise InvalidArgument("Timed out waiting for subclass.")
            subclass = await search_and_select(ctx, subclass_choices, subclass_response.content,
                                               lambda e: e.name)
        else:
            subclass = None

        await ctx.send(author.mention + " What background?")
        try:
            bg_response = await self.bot.wait_for('message', timeout=90, check=chk)
        except asyncio.TimeoutError:
            raise InvalidArgument("Timed out waiting for background.")
        background_choices = await available(ctx, compendium.backgrounds, 'background')
        background = await search_and_select(ctx, background_choices, bg_response.content, lambda e: e.name)
        return race, _class, subclass, background

    async def send_character_details(self, ctx, final_level, race=None, _class=None, subclass=None, background=None):
        loadingMessage = await ctx.channel.send("Generating character, please wait...")
        color = random.randint(0, 0xffffff)

        # Name Gen
        #    DMG name gen
        name = self.old_name_gen()
        # Stat Gen
        #    4d6d1
        #        reroll if too low/high
        stats = [roll('4d6kh3').total for _ in range(6)]
        await ctx.author.send("**Stats for {0}:** `{1}`".format(name, stats))
        # Race Gen
        #    Racial Features
        race = race or random.choice(await available(ctx, compendium.races, 'race'))

        embed = EmbedWithAuthor(ctx)
        embed.title = race.name
        embed.add_field(name="Speed", value=race.speed)
        embed.add_field(name="Size", value=race.size)
        if race.ability:
            embed.add_field(name="Ability Bonuses", value=race.ability)
        for t in race.traits:
            embeds.add_fields_from_long_text(embed, t.name, t.text)
        embed.set_footer(text=f"Race | {race.source_str()}")

        embed.colour = color
        await ctx.author.send(embed=embed)

        # Class Gen
        #    Class Features

        # class
        _class = _class or random.choice(await available(ctx, compendium.classes, 'class'))
        subclass = subclass or (random.choice(subclass_choices)
                                if (subclass_choices := await available(ctx, _class.subclasses, 'subclass')) else None)
        embed = EmbedWithAuthor(ctx)
        embed.title = _class.name
        embed.add_field(name="Hit Die", value=_class.hit_die)
        embed.add_field(name="Saving Throws", value=', '.join(ABILITY_MAP.get(p) for p in _class.saves))

        levels = []
        starting_profs = str(_class.proficiencies)
        starting_items = f"You start with the following items, plus anything provided by your background.\n" \
                         f"{_class.equipment}"
        for l in range(1, 21):
            lvl = _class.levels[l - 1]
            levels.append(', '.join([feature.name for feature in lvl]))

        embed.add_field(name="Starting Proficiencies", value=starting_profs, inline=False)
        embed.add_field(name="Starting Equipment", value=starting_items, inline=False)

        level_features_str = ""
        for i, l in enumerate(levels):
            level_features_str += f"`{i + 1}` {l}\n"
        embed.description = level_features_str
        await ctx.author.send(embed=embed)

        # level table
        embed = EmbedWithAuthor(ctx)
        embed.title = f"{_class.name}, Level {final_level}"

        for resource, value in zip(_class.table.headers, _class.table.levels[final_level - 1]):
            if value != '0':
                embed.add_field(name=resource, value=value)

        embed.colour = color
        await ctx.author.send(embed=embed)

        # features
        embed_queue = [EmbedWithAuthor(ctx)]
        num_fields = 0

        def inc_fields(ftext):
            nonlocal num_fields
            num_fields += 1
            if num_fields > 25:
                embed_queue.append(EmbedWithAuthor(ctx))
                num_fields = 0
            if len(str(embed_queue[-1].to_dict())) + len(ftext) > 5800:
                embed_queue.append(EmbedWithAuthor(ctx))
                num_fields = 0

        def add_levels(source):
            for level in range(1, final_level + 1):
                level_features = source.levels[level - 1]
                for f in level_features:
                    for field in embeds.get_long_field_args(f.text, f.name):
                        inc_fields(field['value'])
                        embed_queue[-1].add_field(**field)

        add_levels(_class)
        if subclass:
            add_levels(subclass)

        for embed in embed_queue:
            embed.colour = color
            await ctx.author.send(embed=embed)

        # Background Gen
        #    Inventory/Trait Gen
        background = background or random.choice(await available(ctx, compendium.backgrounds, 'background'))
        embed = EmbedWithAuthor(ctx)
        embed.title = background.name
        embed.set_footer(text=f"Background | {background.source_str()}")

        ignored_fields = ['suggested characteristics', 'personality trait', 'ideal', 'bond', 'flaw', 'specialty',
                          'harrowing event']
        for trait in background.traits:
            if trait.name.lower() in ignored_fields:
                continue
            text = textwrap.shorten(trait.text, width=1020, placeholder="...")
            embed.add_field(name=trait.name, value=text, inline=False)
        embed.colour = color
        await ctx.author.send(embed=embed)

        out = f"{ctx.author.mention}\n" \
              f"{name}, {race.name} {subclass.name if subclass else ''} {_class.name} {final_level}. " \
              f"{background.name} Background.\n" \
              f"Stat Array: `{stats}`\nI have PM'd you full character details."

        await loadingMessage.edit(content=out)

    @staticmethod
    def old_name_gen():
        name = ""
        beginnings = ["", "", "", "", "A", "Be", "De", "El", "Fa", "Jo", "Ki", "La", "Ma", "Na", "O", "Pa", "Re", "Si",
                      "Ta", "Va"]
        middles = ["bar", "ched", "dell", "far", "gran", "hal", "jen", "kel", "lim", "mor", "net", "penn", "quill",
                   "rond", "sark", "shen", "tur", "vash", "yor", "zen"]
        ends = ["", "a", "ac", "ai", "al", "am", "an", "ar", "ea", "el", "er", "ess", "ett", "ic", "id", "il", "is",
                "in", "or", "us"]
        name += random.choice(beginnings) + random.choice(middles) + random.choice(ends)
        name = name.capitalize()
        return name


def setup(bot):
    bot.add_cog(CharGenerator(bot))
