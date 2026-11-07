"""Inject entrance animations and slide transitions into OOXML.

python-pptx has no animation API, so we build the p:timing XML ourselves and
insert it into each slide part in schema order (cSld, clrMapOvr, transition,
timing). Entrances are addressed by shape name (set at compile time).

Supported:
  effect: fade | fly-up
  start : click (onClick) | after (after previous) | with (with previous)
"""

from lxml import etree
from pptx.oxml.ns import qn

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS = {"p": P, "a": A}


def _e(tag, **attrs):
    el = etree.SubElement  # placeholder, see builder below
    return tag, attrs


class IdGen:
    def __init__(self):
        self.n = 2

    def __call__(self):
        self.n += 1
        return str(self.n)


def _set_visibility(spid, ids, val="visible"):
    return f"""
<p:set>
 <p:cBhvr>
  <p:cTn id="{ids()}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>
  <p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>
  <p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>
 </p:cBhvr>
 <p:to><p:strVal val="{val}"/></p:to>
</p:set>"""


def _fade_block(spid, ids, dur=500):
    return _set_visibility(spid, ids) + f"""
<p:animEffect transition="in" filter="fade">
 <p:cBhvr>
  <p:cTn id="{ids()}" dur="{dur}"/>
  <p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>
 </p:cBhvr>
</p:animEffect>"""


def _fly_block(spid, ids, dur=500):
    return _set_visibility(spid, ids) + f"""
<p:animMotion origin="layout" path="M 0 0.25 L 0 0 E" pathEditRelative="0">
 <p:cBhvr>
  <p:cTn id="{ids()}" dur="{dur}" fill="hold"/>
  <p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>
 </p:cBhvr>
</p:animMotion>"""


def _preset_par(spid, effect, node_type, ids, grp_id):
    preset = {"fade": (10, 0), "fly-up": (2, 4)}.get(effect, (10, 0))
    pid, subtype = preset
    body = _fade_block(spid, ids) if effect == "fade" else _fly_block(spid, ids)
    return f"""
        <p:par>
         <p:cTn id="{ids()}" presetID="{pid}" presetClass="entr" presetSubtype="{subtype}"
                fill="hold" grpId="{grp_id}" nodeType="{node_type}">
          <p:stCondLst><p:cond delay="0"/></p:stCondLst>
          <p:childTnLst>{body}
          </p:childTnLst>
         </p:cTn>
        </p:par>"""


def timing_xml(anims, name_to_id):
    ids = IdGen()
    preset_pars, grp_id = [], 0
    for a in anims:
        spid = name_to_id.get(a.get("target"))
        if not spid:
            continue
        start = a.get("start", "after")
        node_type = {"click": "clickEffect", "with": "withEffect"}.get(start, "afterEffect")
        # first effect always starts the click group
        if not preset_pars:
            node_type = "clickEffect"
        preset_pars.append(_preset_par(spid, a.get("effect", "fade"), node_type,
                                       ids, grp_id))
        grp_id += 1
    if not preset_pars:
        return None
    return f"""<p:timing xmlns:p="{P}" xmlns:a="{A}">
 <p:tnLst>
  <p:par>
   <p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">
    <p:childTnLst>
     <p:seq concurrent="1" nextAc="seek">
      <p:cTn id="{ids()}" dur="indefinite" nodeType="mainSeq">
       <p:childTnLst>
        <p:par>
         <p:cTn id="{ids()}" fill="hold">
          <p:stCondLst><p:cond delay="indefinite"/></p:stCondLst>
          <p:childTnLst>
           <p:par><p:cTn id="{ids()}" fill="hold">
            <p:stCondLst><p:cond delay="0"/></p:stCondLst>
            <p:childTnLst>
             <p:par><p:cTn id="{ids()}" fill="hold">
              <p:stCondLst><p:cond delay="0"/></p:stCondLst>
              <p:childTnLst>{''.join(preset_pars)}
              </p:childTnLst>
             </p:cTn></p:par>
            </p:childTnLst>
           </p:cTn></p:par>
          </p:childTnLst>
         </p:cTn>
        </p:par>
       </p:childTnLst>
      </p:cTn>
      <p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>
      <p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>
     </p:seq>
    </p:childTnLst>
   </p:cTn>
  </p:par>
 </p:tnLst>
</p:timing>"""


def transition_xml(kind="fade"):
    inner = "<p:fade/>" if kind == "fade" else "<p:fade/>"
    return f"""<p:transition xmlns:p="{P}" xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main" spd="med">{inner}</p:transition>"""


def _name_map(slide_part):
    mapping = {}
    for sp in slide_part.shapes:
        try:
            mapping[sp.name] = str(sp.shape_id)
        except Exception:
            continue
    return mapping


def inject_slide(slide_part, anims=None, transition=None):
    spTree = slide_part._element
    # remove any pre-existing timing / transition
    for tag in ("p:timing", "p:transition"):
        for el in spTree.findall(qn(tag)):
            spTree.remove(el)

    if transition:
        t = etree.fromstring(transition_xml(transition).encode("utf-8"))
        spTree.append(t)

    if anims:
        mapping = _name_map(slide_part)
        xml = timing_xml(anims, mapping)
        if xml:
            el = etree.fromstring(xml.encode("utf-8"))
            spTree.append(el)


def apply_animations(prs, slides_meta):
    """slides_meta: list aligned to prs.slides of {'anims':..., 'transition':...}."""
    for slide, meta in zip(prs.slides, slides_meta):
        inject_slide(slide, meta.get("anims"), meta.get("transition"))
