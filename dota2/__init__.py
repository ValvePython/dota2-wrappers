import os
import copy

import vdf
import vpk

import hero

__version__ = "0.1"
__author = "Rossen Goergiev"


class Dota2(object):
    def __init__(self, gamedir=None):
        assert gamedir, "Expected gamedir argument to be set"

        self.gamedir = gamedir
        self.pak1 = vpk.VPK(os.path.join(gamedir, "pak01_dir.vpk"))
        self._items = None
        self._abilities = None
        self._heroes = None
        self.builds = hero.builds

    def __repr__(self):
        return "%s(gamedir=%s)" % (self.__class__.__name__, repr(self.gamedir))

    @property
    def heroes(self):
        if not self._heroes:
            self._heroes = vdf.load(self.pak1.get_file("scripts/npc/npc_heroes.txt"))
            self._heroes = self._heroes['DOTAHeroes']
            del self._heroes['Version']
        return self._heroes

    @property
    def abilities(self):
        if not self._abilities:
            self._abilities = vdf.load(self.pak1.get_file("scripts/npc/npc_abilities.txt"))
            self._abilities = self._abilities['DOTAAbilities']
            del self._abilities['Version']
        return self._abilities

    @property
    def items(self):
        if not self._items:
            self._items = vdf.load(self.pak1.get_file("scripts/npc/items.txt"))
            self._items = self._items['DOTAAbilities']
            del self._items['Version']
        return self._items

    def get_hero(self, name):
        if name not in self.heroes:
            if "npc_dota_hero_" + name in self.heroes:
                name = "npc_dota_hero_" + name
            else:
                found = False
                name = name.lower().replace("'", '').replace("-", '_').replace(' ', '_')
                for key, v in self.heroes.items():
                    if 'url' in v:
                        if v['url'].lower().replace('-', '_') == name:
                            name = key
                            found = True
                            break

                if not found:
                    raise ValueError("Can't find a hero named %s", repr(name))

        return Hero(name, self)

    def get_ability(self, name):
        if name not in self.abilities:
            raise ValueError("Can't find a skill named %s", repr(name))

        return Ability(name, self)

    def _get_set(self, key):
        values = set()
        for v in self.abilities.values():
            if key in v:
                values = values.union(set(map(lambda x: x.strip(), v[key].split("|"))))

        return values.difference(set(['']))

    @property
    def ability_types(self):
        return self._get_set('AbilityType')

    @property
    def ability_damage_types(self):
        return self._get_set('AbilityUnitDamageType')

    @property
    def ability_behaviors(self):
        return self._get_set('AbilityBehavior')

    def get_item(self, name):
        if name not in self.items:
            raise ValueError("Can't find a skill named %s", repr(name))

        return Item(name, self)


class Hero(object):
    # every hero has this basic stats
    base_hp = 150
    base_mana = 0
    base_armor = 0

    # constants
    str_hp_per_pt = 19
    str_regen_per_pt = 0.03
    agi_armor_per_pt = 0.14
    agi_speed_per_pt = 1
    int_mana_per_pt = 14
    int_mana_regen_per_pt = 0.04

    def __init__(self, name, game):
        assert isinstance(game, Dota2), "Expected game parameter to be an instance of Dota2"

        self.name = name
        self.game = game
        self.data = copy.deepcopy(game.heroes['npc_dota_hero_base'])
        self.data.update(game.heroes[name])

        self._level = 1
        self._abilities = []
        self.abilities_map = {}
        self.inventory = []

        # init standard build
        self.build = tuple()
        self._build_ref = None
        self.load_standard_build()

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, repr(self.name))

    @property
    def id(self):
        return int(self.data['HeroID'])

    @property
    def level(self):
        return self._level

    @level.setter
    def level(self, level):
        if level > 25 or level < 1:
            raise ValueError("Invalid value for level, only 1-25")

        if level != self._level:
            self._level = level
            self._update_ability_levels()

    def set_level(self, level):
        self.level = level
        return self

    @property
    def build_friendly_view(self):
        return [(level+1, self.abilities[index].name) for level, index in enumerate(self.build)]

    @property
    def abilities(self):
        if len(self._abilities) == 0:
            self.abilities_map = {}
            index = 1
            while True:
                key = "Ability%d" % index

                if key not in self.data:
                    break

                ability_name = self.data[key]

                if ability_name == '':
                    self._abilities.append(None)
                else:
                    self._abilities.append(self.game.get_ability(ability_name))
                    self.abilities_map[ability_name] = index - 1

                index += 1

        return self._abilities

    def load_standard_build(self):
        if self.name in self.game.builds:
            build = self.game.builds[self.name]
            amap = {ability.id: idx
                    for idx, ability in enumerate(self.abilities) if ability}
            build = map(lambda x: amap[x], build)
            self.build = tuple(build + [build[-1]] * 7)
        self._update_ability_levels()

    def load_bot_build(self):
        if 'Bot' in self.data and 'Build' in self.data['Bot']:
            _ = self.abilities  # initialize abilities_map
            self.build = tuple(map(lambda name: self.abilities_map[name[1]],
                                   sorted(self.data['Bot']['Build'].items(),
                                          key=lambda x: int(x[0]))
                                   )
                               )

        # not all heroes have a bot build
        else:
            self.build = tuple()

        self._update_ability_levels()

    def _update_ability_levels(self):
        build_for_level = self.build[:self.level]

        for idx, ability in enumerate(self.abilities):
            if ability:
                ability.level = build_for_level.count(idx)

    def _ability_attr_contributions(self, attr_name):
        # if build has changed, set the levels for each ability of the hero
        if self.build is not self._build_ref:
            self._build_ref = self.build
            self._update_ability_levels()

        value = [getattr(ability, attr_name, 0)
                 for ability in self.abilities if isinstance(ability, Ability)]
        value += [getattr(item, attr_name, 0)
                  for item in self.inventory if isinstance(item, Item)]

        return value

    def _sum_ability_attr_contributions(self, attr_name):
        return sum(self._ability_attr_contributions(attr_name))

    @property
    def str_base(self):
        return float(self.data['AttributeBaseStrength'])

    @property
    def str_gain(self):
        return float(self.data['AttributeStrengthGain'])

    @property
    def str(self):
        value = self.str_base + self.str_gain * (self.level-1)
        value += self._sum_ability_attr_contributions('bonus_str')
        return value

    @property
    def agi_base(self):
        return float(self.data['AttributeBaseAgility'])

    @property
    def agi_gain(self):
        return float(self.data['AttributeAgilityGain'])

    @property
    def agi(self):
        value = self.agi_base + self.agi_gain * (self.level-1)
        value += self._sum_ability_attr_contributions('bonus_agi')
        return value

    @property
    def int_base(self):
        return float(self.data['AttributeBaseIntelligence'])

    @property
    def int_gain(self):
        return float(self.data['AttributeIntelligenceGain'])

    @property
    def int(self):
        value = self.int_base + self.int_gain * (self.level-1)
        value += self._sum_ability_attr_contributions('bonus_int')
        return value

    @property
    def hp(self):
        hp = self.base_hp
        hp += self.str * self.str_hp_per_pt
        hp += self._sum_ability_attr_contributions('bonus_hp')
        return hp

    @property
    def hp_regen(self):
        regen = float(self.data['StatusHealthRegen'])
        regen += self.str * self.str_regen_per_pt
        return regen

    @property
    def mana(self):
        mana = self.base_mana
        mana += self.int * self.int_mana_per_pt
        mana += self._sum_ability_attr_contributions('bonus_mana')
        return mana

    @property
    def armor(self):
        armor = float(self.data['ArmorPhysical']) + self.base_armor
        armor += self.agi * self.agi_armor_per_pt
        armor += self._sum_ability_attr_contributions('bonus_armor')
        return armor

    @property
    def armor_multiplier(self):
        return 1 - 0.06 * self.armor / (1 + 0.06 * abs(self.armor))

    @property
    def magic_resistance(self):
        return (1 - self.magic_resistance_multiplier) * 100

    @property
    def magic_resistance_multiplier(self):
        values = [1 - float(self.data['MagicalResistance'])/100]
        values += self._ability_attr_contributions('magic_resistance_multiplier')

        return reduce(lambda a, b: a*b, values)

    @property
    def attack_rate(self):
        return float(self.data['AttackRate']) + self.agi

    @property
    def attack_damage(self):
        value = {
            'DOTA_ATTRIBUTE_STRENGTH': self.str,
            'DOTA_ATTRIBUTE_AGILITY': self.agi,
            'DOTA_ATTRIBUTE_INTELLECT': self.int,
        }[self.data['AttributePrimary']]

        value *= 2
        value += float(self.data['AttackDamageMax'])
        value += float(self.data['AttackDamageMax'])
        value = value // 2
        return value


class Ability(object):
    def __init__(self, name, game):
        assert isinstance(game, Dota2), "Expected game parameter to be an instance of Dota2"

        self.name = name
        self.game = game
        self.data = copy.deepcopy(game.abilities['ability_base'])
        self.data.update(game.abilities[name])
        self._parse_special()
        self._level = 1

    def __repr__(self):
        return "%s(%s, level=%d)" % (self.__class__.__name__, repr(self.name), self.level)

    def _parse_special(self):
        self.data_special = {}

        if "AbilitySpecial" in self.data:
            for v in self.data['AbilitySpecial'].values():
                self.data_special.update(v)
            if 'var_type' in self.data_special:
                del self.data_special['var_type']

    def _value(self, value):
        value = value.split(' ')
        return float(value[min(self.level, len(value))-1]) if self.level > 0 else 0.0

    def _get_value(self, key, special=False):
        try:
            return self._value(getattr(self, 'data_special' if special else 'data')[key])
        except KeyError:
            return 0.0

    def _get_value_sp(self, key):
        return self._get_value(key, special=True)

    @property
    def id(self):
        return int(self.data['ID'])

    @property
    def level(self):
        return self._level

    @level.setter
    def level(self, level):
        if level < 0:
            raise ValueError("Invalid value for level, level >= 0")
        self._level = level

    def set_level(self, level):
        self.level = level
        return self

    @property
    def damage(self):
        value = self._get_value('AbilityDamage')
        value += self._get_value_sp('damage')
        return value

    @property
    def cooldown(self):
        return self._get_value('AbilityCooldown')

    @property
    def manacost(self):
        return self._get_value('AbilityManaCost')

    @property
    def bonus_agi(self):
        value = self._get_value_sp('bonus_agility')
        value += self._get_value_sp('marksmanship_agility_bonus')
        value += self._get_value_sp('attribute_bonus_per_level') * min(self.level, 10)
        return value

    @property
    def bonus_int(self):
        value = self._get_value_sp('bonus_intelligence')
        value += self._get_value_sp('attribute_bonus_per_level') * min(self.level, 10)
        return value

    @property
    def bonus_str(self):
        value = self._get_value_sp('bonus_strength')
        value += self._get_value_sp('attribute_bonus_per_level') * min(self.level, 10)
        return value

    @property
    def bonus_hp(self):
        value = self._get_value_sp('bonus_health')
        return value

    @property
    def bonus_mana(self):
        value = self._get_value_sp('bonus_mana')
        return value

    @property
    def magic_resistance(self):
        return (1 - self.magic_resistance_multiplier) * 100

    @property
    def magic_resistance_multiplier(self):
        # abilities
        value = 1 - self._get_value_sp('spell_shield_resistance') / 100
        value *= 1 - self._get_value_sp('bonus_magic_resistance') / 100
        value *= 1 - self._get_value_sp('magic_damage_reduction_pct') / 100
        value *= 1 - self._get_value_sp('flesh_heap_magic_resist') / 100
        value *= 1 - (self._get_value_sp('bonus_resist') * self._get_value_sp('max_layers')) / 100
        # still abilties, but in items.txt
        value *= 1 - self._get_value_sp('bonus_spell_resist') / 100
        value *= 1 - self._get_value_sp('bonus_magical_armor') / 100
        value *= 1 - self._get_value_sp('magic_resistance') / 100

        return value
        # why does every spell have a different attribute to specify magic resistance? vOv


# items are essentually abilities
class Item(Ability, object):
    def __init__(self, name, game):
        assert isinstance(game, Dota2), "Expected game parameter to be an instance of Dota2"

        self.name = name
        self.game = game
        self.data = copy.deepcopy(game.abilities['ability_base'])
        self.data.update(game.items[name])
        self._parse_special()
        self._level = int(self.data.get('ItemBaseLevel', 1))

    @property
    def bonus_agi(self):
        value = self._get_value_sp('bonus_agility')
        value += self._get_value_sp('bonus_stats')
        value += self._get_value_sp('bonus_all_stats')
        return value

    @property
    def bonus_int(self):
        value = self._get_value_sp('bonus_intellect')
        value += self._get_value_sp('bonus_intelligence')
        value += self._get_value_sp('bonus_stats')
        value += self._get_value_sp('bonus_all_stats')
        return value

    @property
    def bonus_str(self):
        value = self._get_value_sp('bonus_strength')
        value += self._get_value_sp('bonus_stats')
        value += self._get_value_sp('bonus_all_stats')
        return value
