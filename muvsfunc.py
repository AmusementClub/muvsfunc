import vapoursynth as vs
import havsfunc as haf
import mvsfunc as mvf
import math

'''
Functions:
    LDMerge
    Compare
    ExInpand
    InDeflate
    MultiRemoveGrain
    GradFun3
    AnimeEdgeMask (2)
    PolygonExInpand
    Luma

    ediaa
    nnedi3aa
    maa
    SharpAAMcmod
    TEdge
    Sort
    Soothe_mod
    TemporalSoften
'''

def LDMerge(flt_h, flt_v, src, mrad=0, show=0, planes=None, convknl=1, conv_div=None):
    """A filter to merge two filtered clip based on gradient direction map from source clip.

    Args:
        flt_h, flt_v: Two filtered clip.
        src: Source clip. Must matc the filtered clip.
        mrad: (int) Expanding of gradient direction map. Default is 0.
        show: (bint) Whether to output gradient direction map. Default is False.
        planes: (int []) Whether to process the corresponding plane. By default, every plane will be processed.
            The unprocessed planes will be copied from the first clip, "flt_h".
        convknl: (int, 0 or 1) Which convolution kernel for gradient direction map generation to use. Default is 1.
        conv_div: (int) Divisor in convolution filter. Default is the max value in convolution kernel.

    """

    core = vs.get_core()
    funcName = 'LDMerge'
    
    if not isinstance(src, vs.VideoNode):
        raise TypeError(funcName + ': \"src\" must be a clip!')
         
    if not isinstance(flt_h, vs.VideoNode):
        raise TypeError(funcName + ': \"flt_h\" must be a clip!')
    if src.format.id != flt_h.format.id:
        raise ValueError(funcName + ': \"flt_h\" must be of the same format as the src clip!')
    if src.width != flt_h.width or src.height != flt_h.height:
        raise ValueError(funcName + ': \"flt_h\" must be of the same size as the src clip!')
    
    if not isinstance(flt_v, vs.VideoNode):
        raise TypeError(funcName + ': \"flt_v\" must be a clip!')
    if src.format.id != flt_v.format.id:
        raise ValueError(funcName + ': \"flt_v\" must be of the same format as the src clip!')
    if src.width != flt_v.width or src.height != flt_v.height:
        raise ValueError(funcName + ': \"flt_v\" must be of the same size as the src clip!')   
        
    if not isinstance(mrad, int):
        raise TypeError(funcName + '\"mrad\" must be an int!')

    if not isinstance(show, int):
        raise TypeError(funcName + '\"show\" must be an int!')
    if show not in list(range(0, 4)):
        raise ValueError(funcName + '\"show\" must be in [0, 1, 2, 3]!')
    
    if planes is None:
        planes = list(range(flt_h.format.num_planes))

    bits = flt_h.format.bits_per_sample
    
    if convknl == 0:
        convknl_h = [-1, -1, -1, 2, 2, 2, -1, -1, -1]
        convknl_v = [-1, 2, -1, -1, 2, -1, -1, 2, -1]
    else: # convknl == 1
        convknl_h = [-17, -61, -17, 0, 0, 0, 17, 61, 17]
        convknl_v = [-17, 0, 17, -61, 0, 61, -17, 0, 17]
    
    if conv_div is None:
        conv_div = max(convknl_h)

    hmap = core.std.Convolution(src, matrix=convknl_h, saturate=False, planes=planes, divisor=conv_div)
    vmap = core.std.Convolution(src, matrix=convknl_v, saturate=False, planes=planes, divisor=conv_div)

    if mrad > 0:
        hmap = haf.mt_expand_multi(hmap, sw=0, sh=mrad, planes=planes)
        vmap = haf.mt_expand_multi(vmap, sw=mrad, sh=0, planes=planes)
    elif mrad < 0:
        hmap = haf.mt_inpand_multi(hmap, sw=0, sh=-mrad, planes=planes)
        vmap = haf.mt_inpand_multi(vmap, sw=-mrad, sh=0, planes=planes)
    
    ldexpr = 'y x x * y y * + sqrt / {peak} *'.format(peak=(1 << bits) - 1)
    ldmap = core.std.Expr([hmap, vmap], [(ldexpr if i in planes else '') for i in range(src.format.num_planes)])

    if show == 0:
        return core.std.MaskedMerge(flt_h, flt_v, ldmap, planes=planes)
    elif show == 1:
        return ldmap
    elif show == 2:
        return hmap
    elif show == 3:
        return vmap

def Compare(src, flt, power=1.5, chroma=False, mode=2):
    """A filter to check the difference of source clip and filtered clip.

    Args:
        src: Source clip.
        flt: Filtered clip.
        power: (float) The variable in the processing kernel which controls the "strength" to increase difference. Default is 1.5.
        chroma: (bint) Whether to process chroma. Default is False.
        mode: (int, 1 or 2) Different processing kernel. 1: non-linear; 2: linear.

    """

    core = vs.get_core()
    funcName = 'Compare'

    if not isinstance(src, vs.VideoNode):
        raise TypeError(funcName + ': \"src\" must be a clip!')
    if src.format.color_family not in [vs.GRAY, vs.YUV, vs.YCOCG]:
        raise TypeError(funcName + ': \"src\" must be a YUV clip!')
    if not isinstance(flt, vs.VideoNode):
        raise TypeError(funcName + ': \"flt\" must be a clip!')
    if src.format.id != flt.format.id:
        raise TypeError(funcName + ': \"src\" and \"flt\" must have the same format')
    if mode not in [1, 2]:
        raise ValueError(funcName + ': \"mode\" must be in [1, 2]!')

    isGray = src.format.color_family == vs.GRAY
    bits = src.format.bits_per_sample

    expr = {}
    expr[1] = 'y x - abs 1 + {power} pow 1 -'.format(power=power)
    expr[2] = 'y x - {scale} * {neutral} +'.format(scale=32768 / (65536 ** (1 / power) - 1), neutral=32768)

    chroma = chroma or isGray

    if bits < 16:
        src = core.fmtc.bitdepth(src, bits=16)
        flt = core.fmtc.bitdepth(flt, bits=16)
        diff = core.std.Expr([src, flt], [expr[mode]] if chroma else [expr[mode], '{neutral}'.format(neutral=32768)])
        diff = core.fmtc.bitdepth(diff, bits=bits, dmode=1, fulls=True, fulld=True)
    else:
        diff = core.std.Expr([src, flt], [expr[mode]] if chroma else [expr[mode], '{neutral}'.format(neutral=32768)])

    return diff

def ExInpand(input, mrad=0, mode='rectangle', planes=None):
    """A filter to use std.Maximum()/std.Minimum() and their mix conveniently.

    Args:
        input: Source clip.
        mrad: (int []) How many times to use std.Maximum()/std.Minimum(). Default is 0.
            Positive value indicates to use std.Maximum().
            Negative value indicates to use std.Minimum().
            Values can be formed into a list, or a list of lists.

            Example:
                mrad=[2, -1] is equvalant to clip.std.Maximum().std.Maximum().std.Minimum()
                mrad=[[2, 1], [2, -1]] is equivalant to
                    haf.mt_expand_multi(clip, sw=2, sh=1).std.Maximum().std.Maximum().std.Minimum()
        mode: (0:"rectangle", 1:"losange" or 2:"ellipse", int or string). Default is "rectangle"
            The shape of the kernel.
        planes: (int []) Whether to process the corresponding plane. By default, every plane will be processed.
            The unprocessed planes will be copied from "input".

    """

    core = vs.get_core()
    funcName = 'ExInpand'

    if not isinstance(input, vs.VideoNode):
        raise TypeError(funcName + ': \"input\" must be a clip!')

    if planes is None:
        planes = list(range(input.format.num_planes))

    if isinstance(mrad, int):
        mrad = [mrad]
    if isinstance(mode, str) or isinstance(mode, int):
        mode = [mode]
    
    if not isinstance(mode, list):
        raise TypeError(funcName + ': \"mode\" must be an int, a string, a list of ints, a list of strings or a list of mixing ints and strings!')

    # internel function
    def ExInpand_process(input, mode=None, planes=None, mrad=None):
        if isinstance(mode, int):
            if mode == 0:
                mode = 'rectangle'
            elif mode == 1:
                mode = 'losange'
            elif mode == 2:
                mode = 'ellipse'
        if isinstance(mode, str):
            mode = mode.lower()
            if mode not in ['rectangle', 'losange', 'ellipse']:
                raise ValueError(funcName + ': \"mode\" must be an int in [0, 2] or a specific string in [\"rectangle\", \"losange\", \"ellipse\"]!')
        else:
            raise TypeError(funcName + ': \"mode\" must be an int in [0, 2] or a specific string in [\"rectangle\", \"losange\", \"ellipse\"]!')
        
        if isinstance(mrad, int):
            sw = mrad
            sh = mrad
        else:
            sw = mrad[0]
            sh = mrad[1]
        
        if sw * sh < 0:
            raise TypeError(funcName + ': \"mrad\" at a time must be both positive or negative!')
        
        if sw > 0 or sh > 0:
            return haf.mt_expand_multi(input, mode=mode, planes=planes, sw=sw, sh=sh)
        else:
            return haf.mt_inpand_multi(input, mode=mode, planes=planes, sw=-sw, sh=-sh)

    # process
    if isinstance(mrad, list):
        if len(mode) < len(mrad):
            mode_length = len(mode)
            for i in range(mode_length, len(mrad)):
                mode.append(mode[mode_length - 1])

        for i in range(len(mrad)):
            if isinstance(mrad[i], list):
                if len(mrad[i]) != 1 and len(mrad[i]) != 2:
                    raise TypeError(funcName + ': \"mrad\" must be an int, a list of ints or a list of a list of two ints!')
                for n in mrad[i]:
                    if not isinstance(n, int):
                        raise TypeError(funcName + ': \"mrad\" must be an int, a list of ints or a list of a list of two ints!')
                if len(mrad[i]) == 1:
                    mrad[i].append(mrad[i][0])
            elif not isinstance(mrad[i], int):
                raise TypeError(funcName + ': \"mrad\" must be an int, a list of ints or a list of a list of two ints!')
            clip = ExInpand_process(input, mode=mode[i], planes=planes, mrad=mrad[i])
    else:
        raise TypeError(funcName + ': \"mrad\" must be an int, a list of ints or a list of a list of two ints!')

    return clip

def InDeflate(input, msmooth=0, planes=None):
    """A filter to use std.Inflate()/std.Deflate() and their mix conveniently.

    Args:
        input: Source clip.
        msmooth: (int []) How many times to use std.Inflate()/std.Deflate(). Default is 0.
            The behaviour is the same as "mode" in ExInpand(). 

        planes: (int []) Whether to process the corresponding plane. By default, every plane will be processed.
            The unprocessed planes will be copied from "input".

    """

    core = vs.get_core()
    funcName = 'InDeFlate'

    if not isinstance(input, vs.VideoNode):
        raise TypeError(funcName + ': \"input\" must be a clip!')

    if planes is None:
        planes = list(range(input.format.num_planes))

    if isinstance(msmooth, int):
        msmoooth = [msmooth]

    # internel function
    def InDeflate_process(input, planes=None, radius=None):
        if radius > 0:
            return haf.mt_inflate_multi(input, planes=planes, radius=radius)
        else:
            return haf.mt_deflate_multi(input, planes=planes, radius=-radius)

    # process
    if isinstance(msmooth, list):
        for m in msmooth:
            if not isinstance(m, int):
                raise TypeError(funcName + ': \"msmooth\" must be an int or a list of ints!')
            else:
                clip = InDeflate_process(input, planes=planes, radius=m)
    else:
        raise TypeError(funcName + ': \"msmooth\" must be an int or a list of ints!')
    
    return clip

def MultiRemoveGrain(input, mode=0, loop=1):
    """A filter to use rgvs.RemoveGrain() and their mix conveniently.

    Args:
        input: Source clip.
        mode: (int []) "mode" in rgvs.RemoveGrain(). Default is 0.
            Can be a list, the logic is similar to "mode" in ExInpand().

            Example: mode=[4, 11, 11] is equivalant to clip.rgvs.RemoveGrain(4).rgvs.RemoveGrain(11).rgvs.RemoveGrain(11)

        loop: (int) How many times the "mode" loops.

    """

    core = vs.get_core()
    funcName = 'MultiRemoveGrain'
    
    if not isinstance(input, vs.VideoNode):
        raise TypeError(funcName + ': \"input\" must be a clip!')

    if isinstance(mode, int):
        mode = [mode]

    if not isinstance(loop, int):
        raise TypeError(funcName + ': \"loop\" must be an int!')
    if loop < 0:
        raise ValueError(funcName + ': \"loop\" must be positive value!')

    if isinstance(mode, list):
        for i in range(loop):
            for m in mode:
                clip = core.rgvs.RemoveGrain(input, mode=m)
    else:
        raise TypeError(funcName + ': \"mode\" must be an int, a list of ints or a list of a list of ints!')

    return clip

def GradFun3(src, thr=None, radius=None, elast=None, mask=None, mode=None, ampo=None, ampn=None,
             pat=None, dyn=None, lsb=None, staticnoise=None, smode=None, thr_det=None,
             debug=None, thrc=None, radiusc=None, elastc=None, planes=None, ref=None):
    """GradFun3 by Firesledge v0.0.1

    Port by Muonium  2016/6/18
    Port from Dither_tools v1.27.2 (http://avisynth.nl/index.php/Dither_tools)
    Currently only smode=1 and smode=2 is implemented in VapourSynth.
    Internal calculation precision is always 16 bits.

    Read the document of Avisynth version for more details.

    Removed parameters list: 
        "dthr", "wmin", "thr_edg", "subspl", "lsb_in"
    Parameters "y", "u", "v" are changed into "planes"

    """

    core = vs.get_core()
    funcName = 'GradFun3'

    if not isinstance(src, vs.VideoNode):
        raise TypeError(funcName + ': \"clip\" must be a clip!')
    if src.format.color_family not in [vs.YUV, vs.GRAY, vs.YCOCG]:
        raise TypeError(funcName + ': \"clip\" must be YUV, GRAY or YCOCG color family!')

    if thr is None:
        thr = 0.35
    elif isinstance(thr, int) or isinstance(thr, float):
        if thr < 0.1 or thr > 10.0:
            raise ValueError(funcName + ': \"thr\" must be in [0.1, 10.0]!')
    else:
        raise TypeError(funcName + ': \"thr\" must be an int or a float!')

    if radius is None:
        radius = 16 if src.width > 1024 or src.height > 576 else 12
    elif isinstance(radius, int):
        if radius <= 0:
            raise ValueError(funcName + '\"radius\" must be strictly positive.')
    else:
        raise TypeError(funcName + '\"radius\" must be an int!')

    if elast is None:
        elast = 3.0
    elif isinstance(elast, int) or isinstance(elast, float):
        if elast < 1:
            raise ValueError(funcName + ':valid range of \"elast\" is [1, +inf)!')
    else:
        raise TypeError(funcName + ': \"elast\" must be an int or a float!')

    if mask is None:
        mask = 2
    elif not isinstance(mask, int):
        raise TypeError(funcName + ': \"mask\" must be an int!')

    if lsb is None:
        lsb = False

    if smode is None:
        smode = 1
    elif smode not in [0, 1, 2, 3]:
        raise ValueError(funcName + ': \"thr\" must be in [0, 1, 2, 3]!')
    if smode == 0:
        if radius not in list(range(1, 68+1)):
            raise ValueError(funcName + ': \"radius\" must be in 1-68 for smode=0 !')
    elif smode == 1:
        if radius not in list(range(1, 128+1)):
            raise ValueError(funcName + ': \"radius\" must be in 1-128 for smode=1 !')

    if thr_det is None:
        thr_det = 2 + round(max(thr - 0.35, 0) / 0.3)
    elif isinstance(thr_det, float):
        if thr_det <= 0.0:
            raise ValueError(funcName + '" \"thr_det\" must be strictly positive!')
    else:
        raise TypeError(funcName + ': \"mask\" must be a float!')

    if debug is None:
        debug = False
    elif not isinstance(debug, bool) and debug not in [0, 1]:
        raise TypeError(funcName + ': \"debug\" must be a bool!')

    if thrc is None:
        thrc = thr
    elif thrc < 0.1 or thrc > 10.0:
        raise ValueError(funcName + ': \"thrc\" must be in [0.1, 10.0]!')

    if radiusc is None:
        radiusc = radius
    elif isinstance(radiusc, int):
        if radiusc <= 0:
            raise ValueError(funcName + '\"radiusc\" must be strictly positive.')
    else:
        raise TypeError(funcName + '\"radiusc\" must be an int!')
    if smode == 0:
        if radiusc not in list(range(1, 68+1)):
            raise ValueError(funcName + ': \"radiusc\" must be in 1-68 for smode=0 !')
    elif smode == 1:
        if radiusc not in list(range(1, 128+1)):
            raise ValueError(funcName + ': \"radiusc\" must be in 1-128 for smode=1 !')

    if elastc is None:
        elastc = elast
    elif isinstance(elastc, int) or isinstance(elastc, float):
        if elastc < 1:
            raise ValueError(funcName + ':valid range of \"elastc\" is [1, +inf)!')
    else:
        raise TypeError(funcName + ': \"elastc\" must be an int or a float!')

    if planes is None:
        planes = list(range(src.format.num_planes))

    if ref is None:
        ref = src
    elif not isinstance(src, vs.VideoNode):
        raise TypeError(funcName + ': \"ref\" must be a clip!')
    if ref.format.color_family not in [vs.YUV, vs.GRAY, vs.YCOCG]:
        raise TypeError(funcName + ': \"ref\" must be YUV, GRAY or YCOCG color family!')

    bits = src.format.bits_per_sample
    src_16 = core.fmtc.bitdepth(src, bits=16, planes=planes) if bits < 16 else src
    src_8 = core.fmtc.bitdepth(src, bits=8, planes=[0]) if bits != 8 else src
    ref_16 = core.fmtc.bitdepth(ref, bits=16, planes=planes) if ref.format.bits_per_sample < 16 else ref

    # Main debanding
    chroma_flag = (thrc != thr or radiusc != radius or
                   elastc != elast) and 0 in planes and (1 in planes or 2 in planes)

    if chroma_flag:
        planes2 = [0] if 0 in planes else []
    else:
        planes2 = planes

    if not planes2:
        raise ValueError(funcName + ': no plane is processed!')

    flt_y = GF3_smooth(src_16, ref_16, smode, radius, thr, elast, planes2)
    if chroma_flag:
        if 0 in planes2:
            planes2.remove(0)
        flt_c = GF3_smooth(src_16, ref_16, smode, radiusc, thrc, elastc, planes2)
        flt = core.std.ShufflePlanes([flt_y, flt_c], list(range(src.format.num_planes)), src.format.color_family)
    else:
        flt = flt_y

    # Edge/detail mask
    td_lo = max(thr_det * 0.75, 1.0)
    td_hi = max(thr_det, 1.0)
    mexpr = 'x {tl} - {th} {tl} - / 255 *'.format(tl=td_lo - 0.0001, th=td_hi+ 0.0001)

    if mask > 0:
        dmask = mvf.GetPlane(src_8, 0)
        dmask = Build_gf3_range_mask(dmask)
        dmask = core.std.Expr([dmask], [mexpr])
        dmask = core.rgvs.RemoveGrain([dmask], [22])
        if mask > 1:
            dmask = core.rgvs.RemoveGrain([dmask], [11])
            if mask > 2:
                dmask = core.std.Convolution(dmask, matrix=[1, 1, 1, 1, 1, 1, 1, 1, 1])
        dmask = core.fmtc.bitdepth(dmask, bits=16)
        res_16 = core.std.MaskedMerge(flt, src_16, dmask, planes=planes, first_plane=True)
    else:
        res_16 = flt

    # Dithering
    result = res_16 if lsb else core.fmtc.bitdepth(res_16, bits=bits, planes=planes, dmode=mode, ampo=ampo,
                                                   ampn=ampn, dyn=dyn, staticnoise=staticnoise, patsize=pat)

    if debug:
        last = mvf.GetPlane(dmask, 0)
        if lsb:
            last = core.fmtc.bitdepth(last, bits=16)
    else:
        last = result

    return last

def GF3_smooth(src_16, ref_16, smode, radius, thr, elast, planes):
    core = vs.get_core()

    if smode == 0:
        return GF3_smoothgrad_multistage(src_16, ref_16, radius, thr, elast, planes)
    elif smode == 1:
        return GF3_dfttest(src_16, ref_16, radius, thr, elast, planes)
    elif smode == 2:
        return GF3_bilateral_multistage(src_16, ref_16, radius, thr, elast, planes)
    elif smode == 3:
        return GF3_smoothgrad_multistage_3(src_16, radius, thr, elast, planes)
    else:
        raise ValueError(funcName + ': wrong smode value!')

def GF3_smoothgrad_multistage(src, ref, radius, thr, elast, planes):
    core = vs.get_core()
    raise RuntimeError(funcName + ': SmoothGrad has not been ported to VapourSynth!')
    '''
    ela_2 = max(elast * 0.83, 1.0)
    ela_3 = max(elast * 0.67, 1.0)
    r2 = radius * 2 // 3
    r3 = radius * 3 // 3
    r4 = radius * 4 // 4
    last = src
    last = SmoothGrad(radius=r2, thr=thr, elast=elast, ref=ref, planes=planes) if r2 >= 1 else last
    last = SmoothGrad(radius=r3, thr=thr * 0.7, elast=ela_2, ref=ref, planes=planes) if r3 >= 1 else last
    last = SmoothGrad(radius=r4, thr=thr * 0.46, elast=ela_3, ref=ref, planes=planes) if r4 >= 1 else last
    return last
    '''

def GF3_smoothgrad_multistage_3(src, radius, thr, elast, planes):
    core = vs.get_core()
    raise RuntimeError(funcName + ': SmoothGrad has not been ported to VapourSynth!')
    '''
    ref = SmoothGrad(src, radius=radius // 3, thr=thr * 0.8, elast=elast)
    last = Boxfilter(src, radius=radius, planes=planes)
    last = Boxfilter(last, radius=radius, planes=planes)
    last = mvf.LimitFilter(last, src, thr=thr * 0.6, elast=elast, ref=ref, planes=planes)
    return last
    '''

def GF3_dfttest(src, ref, radius, thr, elast, planes):
    core = vs.get_core()
    hrad = max(radius * 3 // 4, 1)
    last = core.dfttest.DFTTest(src, sigma=hrad * thr * thr * 32, sbsize=hrad * 4,
                                sosize=hrad * 3, tbsize=1, planes=planes)
    last = mvf.LimitFilter(last, ref, thr=thr, elast=elast, planes=planes)

    return last

def GF3_bilateral_multistage(src, ref, radius, thr, elast, planes):
    core = vs.get_core()

    last = core.bilateral.Bilateral(src, ref=ref, sigmaS=radius / 2, sigmaR=thr / 255, planes=planes, algorithm=0) # Probably error using "thr".

    last = mvf.LimitFilter(last, src, thr=thr, elast=elast, planes=planes)

    return last

def Build_gf3_range_mask(src, radius=1):
    core = vs.get_core()
    last = src

    if radius > 1:
        ma = haf.mt_expand_multi(last, mode='ellipse', planes=[0], sw=radius, sh=radius)
        mi = haf.mt_inpand_multi(last, mode='ellipse', planes=[0], sw=radius, sh=radius)
        last = core.std.Expr([ma, mi], ['x y -'])
    else:
        bits = src.format.bits_per_sample
        black = 0
        white = (1 << bits) - 1
        maxi = core.std.Maximum(last, [0])
        mini = core.std.Minimum(last, [0])
        exp = "x y -"
        exp2 = "x {thY1} < {black} x ? {thY2} > {white} x ?".format(thY1=0, thY2=255, black=black, white=white)
        last = core.std.Expr([maxi,mini],[exp])
        last = core.std.Expr([last], [exp2])

    return last

def AnimeMask(input, shift=0, expr=None, mode=1, resample_args=dict(kernel='bicubic')):
    """A filter to generate edge/ringing mask for anime based on gradient operator.

    For Anime's ringing mask, it's recommended to set "shift" between 0.5 to 1.0.

    Args:
        input: Source clip. Only the First plane will be processed.
        shift: (float, -1.5 ~ 1.5) Location of mask. Default is 0.
        expr: (string) Subsequent processing in std.Expr(). Default is "".
        mode: (-1 or 1) Different kernel. Typically, -1 is for edge, 1 is for ringing. Default is 1.
        resample_args: (dictinary) Which kernel is used to shift the mask. Default is dict(kernel='bicubic').

    """

    core = vs.get_core()
    funcName = 'AnimeMask'
    
    if not isinstance(input, vs.VideoNode):
        raise TypeError(funcName + ': \"input\" must be a clip!')

    if input.format.color_family != vs.GRAY:
        input = mvf.GetPlane(input, 0)

    if mode not in [-1, 1]:
        raise ValueError(funcName + ': \'mode\' have not a correct value! [-1 or 1]')

    if mode == -1:
        input = core.std.Invert(input)
        shift1 = -shift1
        shift2 = -shift2
    
    bits = input.format.bits_per_sample
    
    fmtc_args = dict(fulls=True, fulld=True)
    mask1 = core.std.Convolution(input, [0, 0, 0, 0, 2, -1, 0, -1, 0], saturate=True).fmtc.resample(sx=shift, sy=shift, **fmtc_args, **resample_args)
    mask2 = core.std.Convolution(input, [0, -1, 0, -1, 2, 0, 0, 0, 0], saturate=True).fmtc.resample(sx=-shift, sy=-shift, **fmtc_args, **resample_args)
    mask3 = core.std.Convolution(input, [0, -1, 0, 0, 2, -1, 0, 0, 0], saturate=True).fmtc.resample(sx=shift, sy=-shift, **fmtc_args, **resample_args)
    mask4 = core.std.Convolution(input, [0, 0, 0, -1, 2, 0, 0, -1, 0], saturate=True).fmtc.resample(sx=-shift, sy=shift, **fmtc_args, **resample_args)

    calc_expr = 'x x * y y * + z z * + a a * + sqrt '

    if isinstance(expr, str):
        calc_expr += expr

    mask = core.std.Expr([mask1, mask2, mask3, mask4], [calc_expr])

    if bits != mask.format.bits_per_sample:
        mask = core.fmtc.bitdepth(mask, bits=bits, fulls=True, fulld=True, dmode=1)

    return mask

def AnimeMask2(input, r=1.2, expr=None, mode=1):
    """Yet another filter to generate edge/ringing mask for anime.

    More specifically, it's an approximate Difference of Gaussians filter based on resampling kernel.

    Args:
        input: Source clip. Only the First plane will be processed.
        r: (float, positive) Radius of resampling coefficient. Default is 1.2.
        expr: (string) Subsequent processing in std.Expr(). Default is "".
        mode: (-1 or 1) Different kernel. Typically, -1 is for edge, 1 is for ringing. Default is 1.

    """

    core = vs.get_core()
    funcName = 'AnimeMask2'
    
    if not isinstance(input, vs.VideoNode):
        raise TypeError(funcName + ': \"input\" must be a clip!')

    if input.format.color_family != vs.GRAY:
        input = mvf.GetPlane(input, 0)

    w = input.width
    h = input.height
    bits = input.format.bits_per_sample

    if mode not in [-1, 1]:
        raise ValueError(funcName + ': \'mode\' have not a correct value! [-1 or 1]')

    smooth = core.fmtc.resample(input, haf.m4(w / r), haf.m4(h / r), kernel='bicubic').fmtc.resample(w, h, kernel='bicubic', a1=1, a2=0)
    smoother = core.fmtc.resample(input, haf.m4(w / r), haf.m4(h / r), kernel='bicubic').fmtc.resample(w, h, kernel='bicubic', a1=1.5, a2=-0.25)

    calc_expr = 'x y - ' if mode == 1 else 'y x - '

    if isinstance(expr, str):
        calc_expr += expr

    mask = core.std.Expr([smooth, smoother], [calc_expr])

    if bits != mask.format.bits_per_sample:
        mask = core.fmtc.bitdepth(mask, bits=bits, fulls=True, fulld=True, dmode=1)

    return mask

def PolygonExInpand(input, shift=0, shape=0, mixmode=0, noncentral=False, step=1, amp=1, fmtc_args=dict(), resample_args=dict(kernel='bilinear')):
    """ A filter to process mask based on resampling kernel.

    Args:
        input: Source clip. Only the First plane will be processed.
        shift: (float) How far to expand/inpand. Default is 0.
        shape: (int, 0:losange, 1:square, 2:octagon) The shape of expand/inpand kernel. Default is 0.
        mixmode: (int, 0:max, 1:arithmetic mean, 2:quadratic mean)
            Method used to calculate the mix of different mask. Default is 0.
        noncentral: (bint) Whether to calculate center pixel in mix process.
        step: (float) How far each step of expand/inpand. Default is 1.
        amp: (float) Linear multiple to strengthen the final mask. Default is 1.
        fmtc_args: (dictinary) Extra arguments of fmtc. Default is dict().
        resample_args: (dictinary) Controls which kernel is used to shift the mask. Default is dict(kernel='bilinear').

    """

    core = vs.get_core()
    funcName = 'PolygonExInpand'
    
    if not isinstance(input, vs.VideoNode):
        raise TypeError(funcName + ': \"input\" must be a clip!')

    if shape not in list(range(3)):
        raise ValueError(funcName + ': \'shape\' have not a correct value! [0, 1 or 2]')

    if mixmode not in list(range(3)):
        raise ValueError(funcName + ': \'mixmode\' have not a correct value! [0, 1 or 2]')

    if step <= 0:
        raise ValueError(funcName + ': \'step\' must be positive!')

    invert = False
    if shift < 0:
        invert = True
        input = core.std.Invert(input)
        shift = -shift
    elif shift == 0:
        return input

    bits = input.format.bits_per_sample

    mask5 = input

    while shift > 0:
        step = min(step, shift)
        shift = shift - step

        ortho = [step, step * (1<< input.format.subsampling_h)]
        inv_ortho = [-step, -step * (1<< input.format.subsampling_h)]
        dia = [math.sqrt(step / 2), math.sqrt(step / 2) * (1 << input.format.subsampling_h)]
        inv_dia = [-math.sqrt(step / 2), -math.sqrt(step / 2) * (1 << input.format.subsampling_h)]
        
        # shift
        if shape == 0 or shape == 2:
            mask2 = core.fmtc.resample(mask5, sx=0, sy=ortho, **fmtc_args, **resample_args)
            mask4 = core.fmtc.resample(mask5, sx=ortho, sy=0, **fmtc_args, **resample_args)
            mask6 = core.fmtc.resample(mask5, sx=inv_ortho, sy=0, **fmtc_args, **resample_args)
            mask8 = core.fmtc.resample(mask5, sx=0, sy=inv_ortho, **fmtc_args, **resample_args)

        if shape == 1 or shape == 2:
            mask1 = core.fmtc.resample(mask5, sx=dia, sy=dia, **fmtc_args, **resample_args)
            mask3 = core.fmtc.resample(mask5, sx=inv_dia, sy=dia, **fmtc_args, **resample_args)
            mask7 = core.fmtc.resample(mask5, sx=dia, sy=inv_dia, **fmtc_args, **resample_args)
            mask9 = core.fmtc.resample(mask5, sx=inv_dia, sy=inv_dia, **fmtc_args, **resample_args)

        # mix
        if noncentral:
            expr_list = [
                'x y max z max a max',
                'x y + z + a + 4 /',
                'x x * y y * + z z * + a a * + 4 / sqrt',
                'x y max z max a max b max c max d max e max',
                'x y + z + a + b + c + d + e + 8 /',
                'x x * y y * + z z * + a a * + b b * + c c * + d d * + e e * + 8 / sqrt',
                ]

            if shape == 0 or shape == 1:
                expr = expr_list[mixmode] + ' {amp} *'.format(amp=amp)
                mask5 = core.std.Expr([mask2, mask4, mask6, mask8] if shape == 0 else [mask1, mask3, mask7, mask9], [expr])
            else: # shape == 2
                expr = expr_list[mixmode + 3] + ' {amp} *'.format(amp=amp)
                mask5 = core.std.Expr([mask1, mask2, mask3, mask4, mask6, mask7, mask8, mask9], [expr])
        else: # noncentral == False
            expr_list = [
                'x y max z max a max b max',
                'x y + z + a + b + 5 /',
                'x x * y y * + z z * + a a * + b b * + 5 / sqrt',
                'x y max z max a max b max c max d max e max f max',
                'x y + z + a + b + c + d + e + f + 9 /',
                'x x * y y * + z z * + a a * + b b * + c c * + d d * + e e * + f f * + 9 / sqrt',
                ]

            if (shape == 0) or (shape == 1):
                expr = expr_list[mixmode] + ' {amp} *'.format(amp=amp)
                mask5 = core.std.Expr([mask2, mask4, mask5, mask6, mask8] if shape == 0 else [mask1, mask3, mask5, mask7, mask9], [expr])
            else: # shape == 2
                expr = expr_list[mixmode + 3] + ' {amp} *'.format(amp=amp)
                mask5 = core.std.Expr([mask1, mask2, mask3, mask4, mask5, mask6, mask7, mask8, mask9], [expr])

    if bits != mask5.format.bits_per_sample:
        mask5 = core.fmtc.bitdepth(mask5, bits=bits, dmode=1, **fmtc_args)

    return core.std.Invert(mask5) if invert else mask5

def Luma(input, plane=0, power=4):
    """ std.Lut() implementation of Luma() in Histogram() filter.

    Args:
        input: Source clip. Only the First plane will be processed.
        plane: (int) Which plane to be processed. Default is 0.
        power: (int) Coefficient in processing. Default is 4.

    """

    core = vs.get_core()
    funcName = 'Luma'

    if not isinstance(input, vs.VideoNode):
        raise TypeError(funcname + ': \"input\" must be a clip!')
    
    if (input.format.sample_type != vs.INTEGER):
        raise TypeError(funcname + ': \"input\" must be of integer format!')
        
    bits = input.format.bits_per_sample
    peak = (1 << bits) - 1
    
    clip = mvf.GetPlane(input, plane)
    
    def calc_luma(x):
        p = x << power
        return (peak - (p & peak)) if (p & (peak + 1)) else (p & peak)
    
    return core.std.Lut(clip, function=calc_luma)

def ediaa(a):
    """Suggested by Mystery Keeper in "Denoise of tv-anime" thread

    Read the document of Avisynth version for more details.

    """

    core = vs.get_core()
    funcname = 'ediaa'
    
    if not isinstance(a, vs.VideoNode):
        raise TypeError(funcname + ': \"a\" must be a clip!')

    bits = a.format.bits_per_sample
    
    last = core.eedi2.EEDI2(a, field=1).std.Transpose()
    last = core.eedi2.EEDI2(last, field=1).std.Transpose()
    last = core.fmtc.resample(last, a.width, a.height, [-0.5, -0.5 * (1 << a.format.subsampling_w)], [-0.5, -0.5 * (1 << a.format.subsampling_h)], kernel='spline36')

    if last.format.bits_per_sample == bits:
        return last
    else:
        return core.fmtc.bitdepth(last, bits=bits)

def nnedi3aa(a):
    """Using nnedi3 (Emulgator):

    Read the document of Avisynth version for more details.

    """

    core = vs.get_core()
    funcname = 'nnedi3aa'
    
    if not isinstance(a, vs.VideoNode):
        raise TypeError(funcname + ': \"a\" must be a clip!')

    bits = a.format.bits_per_sample
    
    last = core.nnedi3.nnedi3(a, field=1, dh=True).std.Transpose()
    last = core.nnedi3.nnedi3(last, field=1, dh=True).std.Transpose()
    last = core.fmtc.resample(last, a.width, a.height, [-0.5, -0.5 * (1 << a.format.subsampling_w)], [-0.5, -0.5 * (1 << a.format.subsampling_h)], kernel='spline36')

    if last.format.bits_per_sample == bits:
        return last
    else:
        return core.fmtc.bitdepth(last, bits=bits)
    
def maa(input):
    """ Anti-aliasing with edge masking by martino, mask using "sobel" taken from Kintaro's useless filterscripts and modded by thetoof for spline36

    Read the document of Avisynth version for more details.

    """

    core = vs.get_core()
    funcname = 'maa'
    
    if not isinstance(input, vs.VideoNode):
        raise TypeError(funcname + ': \"input\" must be a clip!')
    
    w = input.width
    h = input.height
    bits = input.format.bits_per_sample
    
    if input.format.color_family != vs.GRAY:
        input_src = input
        input = mvf.GetPlane(input, 0)
    else:
        input_src = None

    mask = core.std.Convolution(input, [0, -1, 0, -1, 0, 1, 0, 1, 0], divisor=2, saturate=False).std.Binarize(haf.scale(7, bits) + 1)   
    aa_clip = core.resize.Spline36(input, w * 2, h * 2)
    aa_clip = core.sangnom.SangNom(aa_clip).std.Transpose()
    aa_clip = core.sangnom.SangNom(aa_clip).std.Transpose()
    aa_clip = core.resize.Spline36(aa_clip, w, h)
    last = core.std.MaskedMerge(input, aa_clip, mask)
    
    if input_src is None:
        return last
    else:
        return core.std.ShufflePlanes([last, input_src], planes=list(range(input_src.format.num_planes)), colorfamily=input_src.format.color_family)

def SharpAAMcmod(orig, dark=0.2, thin=10, sharp=150, smooth=-1, stabilize=False, tradius=2, aapel=1, aaov=None, aablk=None, aatype='nnedi3'):
    """High quality MoComped AntiAliasing script.

    Also a line darkener since it uses edge masking to apply tweakable warp-sharpening,
    "normal" sharpening and line darkening with optional temporal stabilization of these edges.
    Part of AnimeIVTC.
    
    Developed in the "fine anime antialiasing thread".

    Args:
        orig: Source clip. Only the first plane will be processed.
        dark:(float) Strokes darkening strength. Default is 0.2.
        thin:(int) Presharpening. Default is 10.
        sharp:(int) Postsharpening. Default is 150.
        smooth:(int) Postsmoothing. Default is -1
        stabilize:(bint) Use post stabilization with Motion Compensation. Default is False.
        tradius:(int, 1~3) 1 = Degrain1 / 2 = Degrain2 / 3 = Degrain3. Default is 2.
        aapel:(int) Accuracy of the motion estimation. Default is 1
            (Value can only be 1, 2 or 4.
            1 means a precision to the pixel.
            2 means a precision to half a pixel,
            4 means a precision to quarter a pixel,
            produced by spatial interpolation (better but slower).)
        aaov:(int) Block overlap value (horizontal). Default is None.
            Must be even and less than block size.(Higher = more precise & slower)
        aablk:(int, 4, 8, 16, 32, 64, 128) Size of a block (horizontal). Default is 8.
            Larger blocks are less sensitive to noise, are faster, but also less accurate.
        aatype:(string, "sangnom", "eedi2" or "nnedi3"). Default is "nnedi3".
            Use Sangnom() or EEDI2() or NNEDI3() for anti-aliasing.

    """

    core = vs.get_core()
    funcname = 'SharpAAMcmod'
    
    if not isinstance(orig, vs.VideoNode):
        raise TypeError(funcname + ': \"orig\" must be a clip!')
    
    w = orig.width
    h = orig.height
    bits = orig.format.bits_per_sample
    
    if orig.format.color_family != vs.GRAY:
        orig_src = orig
        orig = mvf.GetPlane(orig, 0)
    else:
        orig_src = None
    
    if aaov is None:
        aaov = 8 if w > 1100 else 4
    
    if aablk is None:
        aablk = 16 if w > 1100 else 8
    
    m = core.std.Expr([core.std.Convolution(orig, [5, 10, 5, 0, 0, 0, -5, -10, -5], divisor=4, saturate=False), core.std.Convolution(orig, [5, 0, -5, 10, 0, -10, 5, 0, -5], divisor=4, saturate=False)], ['x y max {neutral8} / 0.86 pow {peak8} *'.format(neutral8=haf.scale(128, bits), peak8=haf.scale(255, bits))])

    if thin == 0 and dark == 0:
        preaa = orig
    elif thin == 0:
        preaa = haf.Toon(orig, str=dark)
    elif dark == 0:
        preaa = core.warp.AWarpSharp2(orig, depth=thin)
    else:
        preaa = haf.Toon(orig, str=dark).warp.AWarpSharp2(depth=thin)
    
    aatype = aatype.lower()
    if aatype == 'sangnom':
        aa = core.resize.Spline36(preaa, w * 2, h * 2)
        aa = core.std.Transpose(aa).sangnom.SangNom()
        aa = core.std.Transpose(aa).sangnom.SangNom()
        aa = core.resize.Spline36(aa, w, h)
    elif aatype == 'eedi2':
        aa = ediaa(preaa)
    elif aatype == 'nnedi3':
        aa = nnedi3aa(preaa)
    else:
        raise ValueError(funcName + ': valid values of \"aatype\" are \"sangnom\", \"eedi2\" and \"nnedi3\"!')
    
    if sharp == 0 and smooth == 0:
        postsh = aa
    else:
        postsh = haf.LSFmod(aa, strength=sharp, overshoot=1, soft=smooth, edgemode=1)
    
    merged = core.std.MaskedMerge(orig, postsh, m)
    
    if stabilize:
        sD = core.std.MakeDiff(orig, merged)
    
        origsuper = haf.DitherLumaRebuild(orig, s0=1).mv.Super(pel=aapel)
        sDsuper = core.mv.Super(sD, pel=aapel)
    
        fv3 = core.mv.Analyse(origsuper, isb=False, delta=3, overlap=aaov, blksize=aablk) if tradius == 3 else None
        fv2 = core.mv.Analyse(origsuper, isb=False, delta=2, overlap=aaov, blksize=aablk) if tradius >= 2 else None
        fv1 = core.mv.Analyse(origsuper, isb=False, delta=1, overlap=aaov, blksize=aablk) if tradius >= 1 else None
        bv1 = core.mv.Analyse(origsuper, isb=True, delta=1, overlap=aaov, blksize=aablk) if tradius >= 1 else None
        bv2 = core.mv.Analyse(origsuper, isb=True, delta=2, overlap=aaov, blksize=aablk) if tradius >= 2 else None
        bv3 = core.mv.Analyse(origsuper, isb=True, delta=3, overlap=aaov, blksize=aablk) if tradius == 3 else None
        
        if tradius == 1:
            sDD = core.mv.Degrain1(sD, sDsuper, bv1, fv1)
        elif tradius == 2:
            sDD = core.mv.Degrain2(sD, sDsuper, bv1, fv1, bv2, fv2)
        elif tradius == 3:
            sDD = core.mv.Degrain3(sD, sDsuper, bv1, fv1, bv2, fv2, bv3, fv3)
        else:
            raise ValueError(funcName + ': valid values of \"tradius\" are 1, 2 and 3!')
        
        reduc = 0.4
        sDD = core.std.Expr([sD, sDD], ['x {neutral} - abs y {neutral} - abs < x y ?'.format(neutral=haf.scale(128, bits))]).std.Merge(sDD, 1.0 - reduc)
    
        last = core.std.MakeDiff(orig, sDD)
    else:
        last = merged
    
    if orig_src is None:
        return last
    else:
        return core.std.ShufflePlanes([last, orig_src], planes=list(range(orig_src.format.num_planes)), colorfamily=orig_src.format.color_family)

def TEdge(input, min=0, max=65535, planes=None, rshift=0):
    """Detect edge using the kernel like TEdgeMask(type=2).

    Port from https://github.com/chikuzen/GenericFilters/blob/2044dc6c25a1b402aae443754d7a46217a2fddbf/src/convolution/tedge.c

    Args:
        input: Source clip.
        min: (int) If output pixel value is lower than this, it will be zero. Default is 0.
        max: (int) If output pixel value is same or higher than this, it will be maximum value of the format. Default is 65535.
        planes: (int []) Whether to process the corresponding plane. By default, every plane will be processed.
            The unprocessed planes will be copied from "input".
        rshift: (int) Shift the output values to right by this count before clamp. Default is 0.

    """

    core = vs.get_core()
    funcName = 'TEdge'

    if not isinstance(input, vs.VideoNode):
        raise TypeError(funcName + ': \"input\" must be a clip!')

    if planes is None:
        planes = list(range(input.format.num_planes))

    rshift = 1 << rshift

    bits = input.format.bits_per_sample
    floor = 0
    peak = (1 << bits) - 1

    gx = core.std.Convolution(input, [4, -25, 0, 25, -4], planes=planes, saturate=False, mode='h')
    gy = core.std.Convolution(input, [-4, 25, 0, -25, 4], planes=planes, saturate=False, mode='v')

    calcexpr = 'x x * y y * + {rshift} / sqrt'.format(rshift=rshift)
    expr = '{calc} {max} > {peak} {calc} {min} < {floor} {calc} ? ?'.format(calc=calcexpr, max=max, peak=peak, min=min, floor=floor)
    return core.std.Expr([gx, gy], [(expr if i in planes else '') for i in range(input.format.num_planes)])

def Sort(input, order=1, planes=None, mode='max'):
    """Simple filter to get nth large value in 3x3.

    Args:
        input: Source clip.
        order: (int) The order of value to get in 3x3 neighbourhood. Default is 1.
        planes: (int []) Whether to process the corresponding plane. By default, every plane will be processed.
            The unprocessed planes will be copied from "input".
        mode: ("max" or "min") How to measure order. Default is "max".

    """

    core = vs.get_core()
    funcName = 'Sort'

    if not isinstance(input, vs.VideoNode):
        raise TypeError(funcName + ': \"input\" must be a clip!')

    if order not in range(1, 10):
        raise ValueError(funcName + ': valid values of \"order\" are 1~9!')

    mode = mode.lower()
    if mode not in ['max', 'min']:
        raise ValueError(funcName + ': valid values of \"mode\" are \"max\" and \"min\"!')

    if planes is None:
        planes = list(range(input.format.num_planes))

    if mode == 'min':
        order = 10 - order # the nth smallest value in 3x3 neighbourhood is the same as the (10-n)th largest value

    if order == 1:
        sort = core.std.Maximum(input, planes=planes)
    elif order in range(2, 5):
        sort = core.rgvs.Repair(core.std.Maximum(input, planes=planes), input, 
                                [(order if i in planes else 0) for i in range(input.format.num_planes)])
    elif order == 5:
        sort = core.std.Median(input, planes=planes)
    elif order in range(6, 9):
        sort = core.rgvs.Repair(core.std.Minimum(input, planes=planes), input, 
                                [((10 - order) if i in planes else 0) for i in range(input.format.num_planes)])
    else: # order == 9
        sort = core.std.Minimum(input, planes=planes)

    return sort

def Soothe_mod(input, source, keep=24, radius=1, scenechange=32, use_misc=False):
    """Modified Soothe().

    Basd on Didée, 6th September 2005, http://forum.doom9.org/showthread.php?p=708217#post708217
    Modified by TheRyuu, 14th July 2007, http://forum.doom9.org/showthread.php?p=1024318#post1024318
    Modified by Muonium, 12th, December 2016, add args "radius", "scenechange" and "use_misc"

    Requires Filters
    misc (optional)

    Args:
        input: Filtered clip.
        source: Source clip. Must match "input" clip.
        keep:(int, 0~100). Minimum percent of the original sharpening to keep. Default is 24.
        radius:(int, 1~7 (use_misc=True) or 1~12 (use_misc=False)) Temporal radius of AverageFrames. Default is 1.
        scenechange:(int) Argument in scenechange detection. Default is 32.
        use_misc:(bint) Whether to use miscellaneous filters. Default is False.

    Examples: (in Avisynth)
        We use LimitedSharpen() as sharpener, and we'll keep at least 20% of its result:
        dull = last
        sharpener = dull.LimitedSharpen( ss_x=1.25, ss_y=1.25, strength=150, overshoot=1 )

        Soothe( sharp, dull, 20 )
 
    """

    core = vs.get_core()
    funcName = 'Soothe_mod'
    
    if not isinstance(input, vs.VideoNode):
        raise TypeError(funcName + ': \"input\" must be a clip!')
    if input.format.color_family != vs.GRAY:
        input = mvf.GetPlane(input, 0)

    if not isinstance(source, vs.VideoNode):
        raise TypeError(funcName + ': \"source\" must be a clip!')
    if source.format.color_family != vs.GRAY:
        source_src = source
        source = mvf.GetPlane(source, 0)
    else:
        source_src = None

    if input.format.id != source.format.id:
        raise TypeError(funcName + ': \"input\" and \"source\" must have the same format')
    
    keep = max(min(keep, 100), 0)
    
    if use_misc:
        if not isinstance(radius, int) or (not(1 <= radius <= 12)):
            raise ValueError(funcName + ': \'radius\' have not a correct value! [1-12]')
    else:
        if not isinstance(radius, int) or (not(1 <= radius <= 7)):
            raise ValueError(funcName + ': \'radius\' have not a correct value! [1-7]')
    
    bits = source.format.bits_per_sample
    
    diff = core.std.MakeDiff(source, input)
    if use_misc:
        diff2 = TemporalSoften(diff, radius, scenechange)
    else:
        diff2 = haf.TemporalSoften(diff, radius, haf.scale(255, bits), 0, scenechange)
    expr = 'x {neutral} - y {neutral} - * 0 < x {neutral} - {KP} * {neutral} + x {neutral} - abs y {neutral} - abs > x {KP} * y {iKP} * + x ? ?'.format(neutral=haf.scale(128, bits), KP=keep/100, iKP=1-keep/100)
    diff3 = core.std.Expr([diff, diff2], [expr])
    
    last = core.std.MakeDiff(source, diff3)

    if source_src is None:
        return last
    else:
        return core.std.ShufflePlanes([last, source_src], planes=list(range(source_src.format.num_planes)), colorfamily=source_src.format.color_family)

def TemporalSoften(input, radius=4, scenechange=15):
    """TemporalSoften filter without thresholding using Miscellaneous filters.

    There will be slight difference in result compare to havsfunc.TemporalSoften().
    It seems that this Misc-filter-based TemporalSoften is slower than the one in havsfunc.

    Read the document of Avisynth version for more details.

    """

    core = vs.get_core()
    funcName = 'TemporalSoften'
    
    if not isinstance(input, vs.VideoNode):
        raise TypeError(funcName + ': \"input\" must be a clip!')

    if scenechange:
        input = core.misc.SCDetect(input, scenechange/255)
    return core.misc.AverageFrames(input, [1 for i in range(2*radius + 1)], scenechange=scenechange)
