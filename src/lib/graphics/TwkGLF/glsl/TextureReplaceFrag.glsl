//
// Copyright (C) 2025 Autodesk, Inc. All Rights Reserved.
//
// SPDX-License-Identifier: Apache-2.0
//
// RV adaptation of twkpaint/shaders/stamp_frag.glsl
// (compat_gl21.glsl macros expanded inline per RV shader convention).
//
// Samples a GL_LUMINANCE brush-tip texture; luminance drives alpha so the
// tip shape is fully defined by the PNG asset. fwidth()-based smoothstep
// provides sub-pixel AA at stamp edges (same technique as ReplaceFrag.glsl).
//
#if __VERSION__ >= 150
#version 150
out vec4 FragColor;
#define FRAGCOLOR FragColor
#else
#define FRAGCOLOR gl_FragColor
#define in varying
#endif

uniform vec4      uniformColor;
uniform sampler2D brushTip;
in vec2 TexCoord0;

void main()
{
    float tip   = texture2D(brushTip, TexCoord0).r;
    float fw    = max(fwidth(tip), 0.001);
    float alpha = smoothstep(0.0, fw, tip);
    FRAGCOLOR   = vec4(uniformColor.rgb, alpha * uniformColor.a);
}
