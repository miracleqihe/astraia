import * as THREE from 'three';

/** The Gemini source's incandescent core, spectral halo and diffraction spikes. */
export function lifeStarMaterial() {
  return new THREE.ShaderMaterial({transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,
    uniforms:{pixelRatio:{value:Math.min(window.devicePixelRatio||1,2)},time:{value:0}},
    vertexShader:`
      attribute float starSize; attribute float starPhase; attribute float starSpike; attribute float starBrightness;
      attribute vec3 nodeColor; uniform float time; uniform float pixelRatio;
      varying vec3 vColor; varying float vSpike; varying float vBrightness;
      void main() {
        vColor=nodeColor; vSpike=starSpike; vBrightness=starBrightness;
        vec4 mvPosition=modelViewMatrix*vec4(position,1.0);
        float twinkle=.90+.10*sin(time*2.1+starPhase);
        float scaleBoost=mix(.65,1.,clamp(starBrightness,0.,1.));
        if(starBrightness>1.05) scaleBoost=1.+(starBrightness-1.)*.55;
        gl_PointSize=clamp(starSize*scaleBoost*twinkle*pixelRatio*(390./max(-mvPosition.z,40.)),1.8*pixelRatio,68.*pixelRatio);
        gl_Position=projectionMatrix*mvPosition;
      }`,
    fragmentShader:`
      varying vec3 vColor; varying float vSpike; varying float vBrightness;
      void main() {
        vec2 uv=gl_PointCoord-vec2(.5); float d=length(uv)*2.; if(d>1.) discard;
        float core=exp(-d*d*34.); float halo=exp(-d*5.6)*.62; float spike=0.;
        if(vSpike>.05) {
          float sx=exp(-abs(uv.y)*46.)*exp(-abs(uv.x)*4.8);
          float sy=exp(-abs(uv.x)*46.)*exp(-abs(uv.y)*4.8);
          vec2 ruv=vec2(uv.x+uv.y,uv.x-uv.y)*.7071;
          float diagonal=(exp(-abs(ruv.y)*65.)*exp(-abs(ruv.x)*9.)+exp(-abs(ruv.x)*65.)*exp(-abs(ruv.y)*9.))*.32;
          spike=(sx+sy+diagonal)*vSpike*.92;
        }
        float alphaMod=clamp(vBrightness,.09,2.2);
        float alpha=clamp((core*1.35+halo+spike)*alphaMod,0.,1.); if(alpha<.012) discard;
        float whiteMix=clamp(core*1.25+spike*.55,0.,1.);
        vec3 color=mix(vColor,vec3(1.,.99,.96),whiteMix);
        gl_FragColor=vec4(color*alphaMod,alpha);
        #include <colorspace_fragment>
      }`,
  });
}
