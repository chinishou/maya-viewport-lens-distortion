// SPDX-License-Identifier: LGPL-3.0-or-later

// - An EXR stores rows top to bottom. Nuke STMap values are *not* EXR row
//   numbers: R is source U (left=0), G is source V (bottom=0, top=1).
// - In Maya's OpenGL Core MQuadRender path, rasterUV.y=0 at the output's top.
//   Maya's EXR texture also exposes its top row at texture V=0. Thus sampling
//   stmap at rasterUV selects the matching output row, without flipping V.
// - scene is an OpenGL render target: texture V=0 reads its bottom row.
//   The G value from the STMap therefore already points to the right source row. 
//
// Each transform maps one normalized UV space into another:
// result = input * transform.xy + transform.zw (scale, then offset).
// Maya currently supplies identity transforms; the offline dataWindow test
// supplies non-identity transforms for EXR overscan. 
vec4 sampleSceneThroughStmap(sampler2D scene, sampler2D stmap, vec2 rasterUV,
                             vec4 outputTransform, vec4 stmapTransform,
                             vec4 sourceTransform)
{
    vec2 outputUV = rasterUV * outputTransform.xy + outputTransform.zw;
    vec2 stmapUV = outputUV * stmapTransform.xy + stmapTransform.zw;
    if (any(lessThan(stmapUV, vec2(0.0))) || any(greaterThan(stmapUV, vec2(1.0))))
        return vec4(0.0);
    // Explicitly use base mip level 0 for both lookups.
    vec2 sourceUV = textureLod(stmap, stmapUV, 0.0).rg;

    // RG may fall outside the displayWindow's 0-1 range; output black only
    // when it falls outside the actual source dataWindow.
    vec2 textureUV = sourceUV * sourceTransform.xy + sourceTransform.zw;
    if (any(lessThan(textureUV, vec2(0.0))) || any(greaterThan(textureUV, vec2(1.0))))
        return vec4(0.0);
    return textureLod(scene, textureUV, 0.0);
}
