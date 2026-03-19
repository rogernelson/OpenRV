//
// Copyright (C) 2025 Autodesk, Inc. All Rights Reserved.
//
// SPDX-License-Identifier: Apache-2.0
//
// Fragment shader for stamp brushes with a texture tip.
// Samples a GL_LUMINANCE brush-tip texture; the luminance value becomes
// the brush alpha so the tip shape is fully controlled by the PNG asset.
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
    // GL_LUMINANCE textures replicate the single channel into r, g, b.
    float alpha    = texture2D(brushTip, TexCoord0).r;
    FRAGCOLOR.rgb  = uniformColor.rgb;
    FRAGCOLOR.a    = alpha * uniformColor.a;
}
