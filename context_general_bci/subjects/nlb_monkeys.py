import numpy as np
from context_general_bci.subjects import SubjectName, SortedArrayInfo, SubjectInfo, SubjectArrayRegistry, GeometricArrayInfo

@SubjectArrayRegistry.register
class Jenkins(SubjectInfo):
    # Churchland maze (NLB)
    name = SubjectName.jenkins
    _arrays = {
        # this is actually just for held-in neurons. `main` is an array used for NLB data
        # technically the data is available to decompose into PMd and M1, but NLB data is sorted
        # so there's no simple map from main to PMd/M1. Hence we make it another pseudo array and hope for the best.
        'main': SortedArrayInfo(_max_channels=137),
        'PMd': GeometricArrayInfo(array=np.arange(96)), # these are _on_ Utah arrays, I just don't have the geometry
        'M1': GeometricArrayInfo(array=np.arange(96) + 96),
    }

@SubjectArrayRegistry.register
class Nitschke(SubjectInfo):
    # Churchland maze + misc, both unsorted two array datasets
    name = SubjectName.nitschke
    _arrays = {
        'PMd': GeometricArrayInfo(array=np.arange(96)),
        'M1': GeometricArrayInfo(array=np.arange(96) + 96),
    }


@SubjectArrayRegistry.register
class Indy(SubjectInfo):
    name = SubjectName.indy
    _arrays = {
        'main': SortedArrayInfo(_max_channels=98), # For NLB
        'M1': GeometricArrayInfo(array=np.arange(96)), # MUA hash unit
        'M1_all': SortedArrayInfo(_max_channels=480), # MUA hash unit, 5 x 96. These are _not_ to be used in non-flat cases, wildly inefficient.
        'S1': GeometricArrayInfo(array=np.arange(96) + 96), # MUA Hash unit (S1 not supported, too many units)
    }

@SubjectArrayRegistry.register
class Loco(SubjectInfo): # RTT https://zenodo.org/record/3854034
    name = SubjectName.loco
    _arrays = {
        'M1': GeometricArrayInfo(array=np.arange(96)),
        'M1_all': SortedArrayInfo(_max_channels=480), # MUA hash unit, 5 x 96
        'S1': GeometricArrayInfo(array=np.arange(96) + 96),
    }

@SubjectArrayRegistry.register
class Mihi(SubjectInfo):
    name = SubjectName.mihi
    _arrays = {
        'main': SortedArrayInfo(_max_channels=187), # single-session (Dyer)
        'M1': SortedArrayInfo(_max_channels=96), # dual
        # 'M1': SortedArrayInfo(_max_channels=52), # dual
        'PMd': SortedArrayInfo(_max_channels=121), # dual
    }

@SubjectArrayRegistry.register
class Chewie(SubjectInfo):
    name = SubjectName.chewie
    _arrays = {
        'main': SortedArrayInfo(_max_channels=241), # single-session (Dyer and Flint)
        'M1': SortedArrayInfo(_max_channels=96), # left hemisphere
        # 'M1': SortedArrayInfo(_max_channels=88), # left hemisphere
        'PMd': SortedArrayInfo(_max_channels=211), # left hemisphere
    }

@SubjectArrayRegistry.register
class Spike(SubjectInfo):
    name = SubjectName.spike
    _arrays = {
        'M1': SortedArrayInfo(_max_channels=96),
    }

@SubjectArrayRegistry.register
class Greyson(SubjectInfo):
    name = SubjectName.greyson
    _arrays = {
        'M1': SortedArrayInfo(_max_channels=96),
    }

@SubjectArrayRegistry.register
class Han(SubjectInfo):
    name = SubjectName.han
    _arrays = {
        'LeftS1Area2': SortedArrayInfo(_max_channels=96), # saw highest 83
    }

@SubjectArrayRegistry.register
class Lando(SubjectInfo):
    name = SubjectName.lando
    _arrays = {
        'LeftS1Area2': SortedArrayInfo(_max_channels=64), # saw highest 46
    }

@SubjectArrayRegistry.register
class Reggie(SubjectInfo):
    name = SubjectName.reggie
    _arrays = {
        'M1': GeometricArrayInfo(array=np.arange(96)), # P sure this guy only has 94 channels but 96 rounds it even and we pad in `churchland_misc`
        'PMd': GeometricArrayInfo(array=np.arange(96) + 94),
    }

@SubjectArrayRegistry.register
class Earl(SubjectInfo):
    name = SubjectName.earl
    _arrays = {
        'M1': SortedArrayInfo(_max_channels=192), # Might as well, just in case
    }

@SubjectArrayRegistry.register
class Rocky(SubjectInfo):
    name = SubjectName.rocky
    _arrays = {
        'M1': SortedArrayInfo(_max_channels=192), # max seen 165
    }

@SubjectArrayRegistry.register
class RockySchwartz(SubjectInfo):
    name = SubjectName.rocky_schwartz
    _arrays = {
        'M1': SortedArrayInfo(_max_channels=192), # max seen 165
    }

@SubjectArrayRegistry.register
class Nigel(SubjectInfo):
    name = SubjectName.nigel
    _arrays = {
        'M1': SortedArrayInfo(_max_channels=96), # max seen 58
    }

@SubjectArrayRegistry.register
class NigelSchwartz(SubjectInfo):
    name = SubjectName.nigel_schwartz
    _arrays = {
        'M1': SortedArrayInfo(_max_channels=192),
    }

@SubjectArrayRegistry.register
class Jango(SubjectInfo):
    name = SubjectName.jango
    _arrays = {
        'M1': SortedArrayInfo(_max_channels=np.arange(96)), # Sometimes not included
        # 'M1': GeometricArrayInfo(array=np.arange(96)),
    }

@SubjectArrayRegistry.register
class RouseP(SubjectInfo):
    name = SubjectName.rouse_p
    _arrays = {
        'M1': SortedArrayInfo(_max_channels=320), # Sorting be crazy
    }

@SubjectArrayRegistry.register
class RouseQ(SubjectInfo):
    name = SubjectName.rouse_q
    _arrays = {
        'M1': SortedArrayInfo(_max_channels=320),
    }

@SubjectArrayRegistry.register
class RouseA(SubjectInfo):
    name = SubjectName.rouse_a
    _arrays = {
        'M1': SortedArrayInfo(_max_channels=320), # Generic motor, actually contains premotor as well.
    }

@SubjectArrayRegistry.register
class RouseB(SubjectInfo):
    name = SubjectName.rouse_b
    _arrays = {
        'M1': SortedArrayInfo(_max_channels=320), # Generic motor, actually contains premotor as well.
    }

@SubjectArrayRegistry.register
class Maestro(SubjectInfo):
    name = SubjectName.maestro
    _arrays = {
        'FEF': SortedArrayInfo(_max_channels=24), # Generic motor, actually contains premotor as well.
    }

@SubjectArrayRegistry.register
class FALCONH1(SubjectInfo):
    name = SubjectName.falcon_h1
    _arrays = {
        'M1': SortedArrayInfo(_max_channels=192),
    }

@SubjectArrayRegistry.register
class FALCONH2(SubjectInfo):
    name = SubjectName.falcon_h2
    _arrays = {
        'M1': SortedArrayInfo(_max_channels=192),
    }

@SubjectArrayRegistry.register
class FALCONM1(SubjectInfo):
    name = SubjectName.falcon_m1
    _arrays = {
        'M1': SortedArrayInfo(_max_channels=192),
    }

@SubjectArrayRegistry.register
class FALCONM2(SubjectInfo):
    name = SubjectName.falcon_m2
    _arrays = {
        'M1': SortedArrayInfo(_max_channels=192),
    }

@SubjectArrayRegistry.register
class PerichC(SubjectInfo):
    name = SubjectName.perich_c
    _arrays = {
        'main': SortedArrayInfo(_max_channels=192),
    }

@SubjectArrayRegistry.register
class PerichJ(SubjectInfo):
    name = SubjectName.perich_j
    _arrays = {
        'main': SortedArrayInfo(_max_channels=192),
    }

@SubjectArrayRegistry.register
class PerichM(SubjectInfo):
    name = SubjectName.perich_m
    _arrays = {
        'main': SortedArrayInfo(_max_channels=192),
    }

@SubjectArrayRegistry.register
class PerichT(SubjectInfo):
    name = SubjectName.perich_t
    _arrays = {
        'main': SortedArrayInfo(_max_channels=192),
    }

@SubjectArrayRegistry.register
class BatistaF(SubjectInfo):
    name = SubjectName.batista_f
    _arrays = {
        'main': SortedArrayInfo(_max_channels=192),
    }

@SubjectArrayRegistry.register
class BatistaE(SubjectInfo):
    name = SubjectName.batista_e
    _arrays = {
        'main': SortedArrayInfo(_max_channels=192), # This is Earl
    }

@SubjectArrayRegistry.register
class HatGeneric(SubjectInfo):
    name = SubjectName.hat_generic
    _arrays = {
        'main': SortedArrayInfo(_max_channels=320),
    }

@SubjectArrayRegistry.register
class ChestekGeneric(SubjectInfo):
    name = SubjectName.chestek_generic
    _arrays = {
        'main': SortedArrayInfo(_max_channels=192),
    }

@SubjectArrayRegistry.register
class LimbLabGeneric(SubjectInfo):
    name = SubjectName.limblab_generic
    _arrays = {
        'main': SortedArrayInfo(_max_channels=320),
    }

@SubjectArrayRegistry.register
class T5(SubjectInfo):
    name = SubjectName.t5
    _arrays = {
        'main': SortedArrayInfo(_max_channels=256),
    }