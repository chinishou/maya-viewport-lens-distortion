// SPDX-License-Identifier: LGPL-3.0-or-later
// Both dataWindow and displayWindow are first converted to UV scale/offset
// with a bottom-left origin.
// transform.xy = scale, transform.zw = offset
vec4 lensDistort(sampler2D scene, sampler2D map, vec2 rasterUV,
              vec4 outputTransform, vec4 mapTransform,
              vec4 sourceTransform)
{
    vec2 outputUV = rasterUV * outputTransform.xy + outputTransform.zw;
    vec2 mapUV = outputUV * mapTransform.xy + mapTransform.zw;
    if (any(lessThan(mapUV, vec2(0.0))) || any(greaterThan(mapUV, vec2(1.0))))
        return vec4(0.0, 0.0, 0.0, 1.0);
    vec2 sourceUV = texture2D(map, mapUV).rg;

    // RG may fall outside the displayWindow's 0-1 range; output black only
    // when it falls outside the actual source dataWindow.
    vec2 textureUV = sourceUV * sourceTransform.xy + sourceTransform.zw;
    if (any(lessThan(textureUV, vec2(0.0))) || any(greaterThan(textureUV, vec2(1.0))))
        return vec4(0.0, 0.0, 0.0, 1.0);
    return texture2D(scene, textureUV);
}