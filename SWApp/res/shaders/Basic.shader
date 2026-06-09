#shader vertex
#version 330 core 

layout(location=0) in vec3 position; 
layout(location=1) in vec3 normal;
layout(location=2) in vec2 texcoord; //贴图坐标
layout(location=3) in mat4 model; 

out VS_OUT{
	vec2 v_texcoord;//传递（vary）给片元着色器的变量
	vec4 v_WorldNormal;
	//vec4 v_ViewNormal;
	vec4 v_WorldPosition;
}vs_out;


layout(std140) uniform Matrices
{
	mat4 u_view;
	mat4 u_projection;
};


void main() 
{ 
	vs_out.v_texcoord=texcoord;
	vs_out.v_WorldNormal=model*vec4(normalize(normal),0.0f);
	//vs_out.v_ViewNormal=u_view*model*vec4(normalize(normal),0.0f);
	vs_out.v_WorldPosition=model*vec4(position,1.0f);
	gl_Position =u_projection*u_view*model*vec4(position,1.0f); 

}




#shader geometry
#version 330 core

// 接收三角形
layout(triangles) in;
// 输出三角形条带，最多3个顶点
layout(triangle_strip, max_vertices = 3) out;

// 从顶点着色器接收的输入块（因为是三角形，所以是一个包含3个元素的数组）
in VS_OUT {
    vec2 v_texcoord;
    vec4 v_WorldNormal;
    vec4 v_WorldPosition;
} gs_in[];

// 发送给片元着色器的输出块
out GS_OUT {
    vec2 v_texcoord;
    vec4 v_WorldNormal;
    vec4 v_WorldPosition;
    vec3 v_Barycentric; // 🌟 新增：传递给片元着色器的重心坐标
} gs_out;

void main() 
{
    // 第 1 个顶点
    gl_Position = gl_in[0].gl_Position;
    gs_out.v_texcoord = gs_in[0].v_texcoord;
    gs_out.v_WorldNormal = gs_in[0].v_WorldNormal;
    gs_out.v_WorldPosition = gs_in[0].v_WorldPosition;
    gs_out.v_Barycentric = vec3(1.0, 0.0, 0.0);
    EmitVertex();

    // 第 2 个顶点
    gl_Position = gl_in[1].gl_Position;
    gs_out.v_texcoord = gs_in[1].v_texcoord;
    gs_out.v_WorldNormal = gs_in[1].v_WorldNormal;
    gs_out.v_WorldPosition = gs_in[1].v_WorldPosition;
    gs_out.v_Barycentric = vec3(0.0, 1.0, 0.0);
    EmitVertex();

    // 第 3 个顶点
    gl_Position = gl_in[2].gl_Position;
    gs_out.v_texcoord = gs_in[2].v_texcoord;
    gs_out.v_WorldNormal = gs_in[2].v_WorldNormal;
    gs_out.v_WorldPosition = gs_in[2].v_WorldPosition;
    gs_out.v_Barycentric = vec3(0.0, 0.0, 1.0);
    EmitVertex();

    // 结束图元
    EndPrimitive();
}




#shader fragment
#version 330 core 

struct Material
{
	sampler2D texture_diffuse1;
	sampler2D texture_specular1;
	//sampler2D texture_normal1;
};

out vec4 color; 

uniform Material material;
uniform vec3 MBDColor;
uniform int isMBDView;
uniform int viewType;
uniform int gsMode;
uniform sampler2D depth_R_map;
uniform sampler2D depth_R_CullF_map;
uniform sampler2D depth_CullF_map;
uniform sampler2D depth_map;
uniform float WinWidth;
uniform float WinHeight;
uniform int distributionDirection;
uniform int xDistribution;
uniform int zDistribution;


//in VS_OUT{
//	vec2 v_texcoord;//从顶点着色器传入的变量
//	vec4 v_WorldNormal;
//	vec4 v_WorldPosition;
//}fs_in;

// 修改这里：必须与几何着色器的输出块名称一致
in GS_OUT {
    vec2 v_texcoord;
    vec4 v_WorldNormal;
    vec4 v_WorldPosition;
    vec3 v_Barycentric; // 即使不用也建议加上，保持结构一致
} fs_in;


void main() 
{
    vec3 worldLight1 = normalize(vec3(1.0f,1.4f,1.2f)); //获取光源位置
    vec3 worldLight2 = normalize(vec3(-1.0f,-1.5f,-1.3f)); //获取光源位置
	vec3 lightColor = vec3(1.0f);
	vec3 diffuseColor = vec3(0.9f);
    vec3 diffuse = lightColor * diffuseColor * (max(0, dot(worldLight1, normalize(fs_in.v_WorldNormal.xyz))) + max(0, dot(worldLight2, normalize(fs_in.v_WorldNormal.xyz)))); // 计算漫反射
	vec3 normal_color = fs_in.v_WorldNormal.xyz*0.5 +vec3(0.5); // 法线
	//float depth = float(gl_FragCoord.z);
	vec2 uv = vec2(gl_FragCoord.x/WinWidth, gl_FragCoord.y/WinHeight);
	float depth_R = texture(depth_R_map,uv).r;
	float depth_R_CullF = texture(depth_R_CullF_map,uv).r;
	float depth_CullF = texture(depth_CullF_map,uv).r;
	float depth = texture(depth_map,uv).r;
	float thickness = 1.0f - (depth_R - depth);//0表示实体最厚
	float thickness_CullF = 1.0f - (depth_R_CullF - depth_CullF);//0表示空腔最厚
	thickness_CullF = thickness_CullF>1.0f? 1.0f:thickness_CullF;
	//float final_thickness = 1.0f - (thickness_CullF - thickness);
	float final_thickness = 1.0f - (depth_CullF - depth);
	diffuse = diffuse - vec3(depth*0.1f);

	vec3 finalColor = vec3(1.0f,0.0f,0.0f);
	if(isMBDView>0){
		finalColor = (gsMode == 1 && viewType > -1 && viewType < 2)? vec3(0.0f,0.0f,MBDColor) : finalColor;
	}
	else{
		finalColor = (gsMode == 1  && viewType == 0)? vec3(1.0f-depth,0.0f,0.0f) : finalColor;/////////////
		finalColor = (gsMode == 1 && viewType == 1)? vec3(0.0f,1.0f-final_thickness,0.0f) : finalColor;
	}
	finalColor = (gsMode == 0 && viewType == 0)? vec3(1.0f-depth,0.0f,0.0f) : finalColor;//////////////
	finalColor = (gsMode == 0 && viewType == 1)? vec3(0.0f,1.0f-final_thickness,0.0f) : finalColor;
	//finalColor.x = (viewType == 1)? final_thickness : finalColor.x;
	//finalColor.x = (viewType == 1 && cullMode == 1)? thickness_CullF : finalColor.x;
	//if(viewType == 1 && cullMode == 0){
	//	finalColor.x = thickness;
	//}
	//finalColor = (isMBDView>0 && viewType < 2)? finalColor : vec3(final_thickness);
	finalColor = viewType > 1 ? diffuse : finalColor;
	//finalColor = (viewType > 2) ? vec3(final_thickness) : finalColor;
	//finalColor = (viewType > 2 && cullMode == 1) ? vec3(1.0f - thickness_CullF + thickness) : finalColor;

	//用于算法比较
	//finalColor = (viewType < 2 && cullMode == 0) ? vec3(thickness) : finalColor;
	//finalColor = (viewType < 2 && cullMode == 1) ? vec3(thickness_CullF) : finalColor;


	finalColor.x = (distributionDirection==1)? (int(fs_in.v_WorldPosition.x>0)*2-1)*(int(xDistribution>0)*2-1) : finalColor.x;
	finalColor.x = (distributionDirection==2)? (int(fs_in.v_WorldPosition.z>0)*2-1)*(int(zDistribution>0)*2-1) : finalColor.x;

	//应力图
	float real_thickness = (gsMode == 0 && viewType == 0)? 1.0f - depth : 0.0f;///////////
	real_thickness = (gsMode == 0 && viewType == 1)? 1.0f - final_thickness : real_thickness;
	real_thickness = (gsMode == 1 && viewType == 0)? MBDColor.x : real_thickness;
	real_thickness = (gsMode == 1 && viewType == 1)? MBDColor.y : real_thickness;

	float TargetThickness = 0.5f;
	float thicknessCut1 = TargetThickness * 2.0f/3.0f;
	float thicknessCut2 = TargetThickness * 2.0f/3.0f*2.0f;
	float thicknessR = -1.0f + real_thickness/thicknessCut1;
	float thicknessG = real_thickness>0.5f? 3.0f - real_thickness*2.0f/thicknessCut2 : real_thickness/thicknessCut1;
	float thicknessB = 2.0f - real_thickness*2.0f/thicknessCut2;
	vec3 densityColor = vec3(thicknessR,thicknessG,thicknessB);

	//finalColor = (viewType < 2)? densityColor : finalColor; //开启应力图
	//finalColor = (viewType == 1)? vec3(MBDColor.x*2,1.0f-depth,(1.0f-final_thickness)*10) : finalColor; //融合

	//分开rgb
	finalColor = (gsMode == 0 && viewType == 0)? vec3(0.0f,real_thickness,0.0f) : finalColor;
	finalColor = (gsMode == 0 && viewType == 1)? vec3(0.0f,0.0f,real_thickness*10) : finalColor;
	finalColor = (gsMode == 1 && viewType == 0)? vec3(real_thickness*2,0.0f,0.0f) : finalColor;
	finalColor = (gsMode == 1 && viewType == 1)? vec3(real_thickness*2,0.0f,0.0f) : finalColor;

	//finalColor = MBDColor;
	//finalColor = diffuse;

	color =vec4(finalColor,1.0f);//*(1.0f-shadowColor) //texColor;//u_color;//vec4(0.2,0.7,0.3,1.0); 
}


// 🌟 修改输入块：接收来自几何着色器的 GS_OUT
//in GS_OUT {
//    vec2 v_texcoord;
//    vec4 v_WorldNormal;
//    vec4 v_WorldPosition;
//    vec3 v_Barycentric; // 🌟 接收重心坐标
//} fs_in;

//void main() 
//{
//    // ==========================================
//    // 🌟 核心新增：科研色彩校正 (Scientific Color Correction)
//    // ==========================================
//    // 1. 计算人眼视觉的真实亮度 (Luminance)
//    float luminance = dot(MBDColor, vec3(0.299, 0.587, 0.114));
//    vec3 grayScale = vec3(luminance);
    
//    // 2. 降低饱和度 (Saturation)
//    // 设为 0.0 是黑白灰，1.0 是原始鲜艳颜色。学术配图推荐 0.4 ~ 0.65
//    float saturation = 0.55; 
//    vec3 desaturatedColor = mix(grayScale, MBDColor, saturation);
    
//    // 3. 混合一点白色以提升明度 (变成高级的粉彩/莫兰迪色)
//    // mix 参数设为 0.2，表示掺入 20% 的纯白
//    vec3 academicColor = mix(desaturatedColor, vec3(1.0), 0.2); 

//    // ==========================================
//    // 1. 计算漫反射光照 (Diffuse Lighting)
//    // ==========================================
//    vec3 worldLight1 = normalize(vec3(1.0f, 1.4f, 1.2f));
//    vec3 worldLight2 = normalize(vec3(-1.0f, -1.5f, -1.3f));
    
//    // 光源颜色也可以稍微柔和一点，避免把模型照得太生硬
//    vec3 lightColor = vec3(0.95f); 
    
//    vec3 normal = normalize(fs_in.v_WorldNormal.xyz);
    
//    float diff1 = max(0.0, dot(worldLight1, normal));
//    float diff2 = max(0.0, dot(worldLight2, normal));
    
//    // 💡 注意：这里使用调色后的 academicColor 代替 MBDColor
//    vec3 diffuseLighting = lightColor * academicColor * (diff1 + diff2);

//    // 提高环境光比例，让模型暗部不至于死黑，这在白底的论文插图中非常重要
//    vec3 ambient = 0.4 * academicColor; 
    
//    vec3 litColor = ambient + diffuseLighting;

//    // ==========================================
//    // 2. 线框边缘检测与抗锯齿 (Wireframe)
//    // ==========================================
//    // 论文配图建议：线框不要用死黑 (0,0,0)，用深灰色 (0.2,0.2,0.2) 视觉更柔和
//    vec3 wireframeColor = vec3(0.25, 0.25, 0.25); 
//    float wireframeWidth = 1.0;               

//    vec3 d = fwidth(fs_in.v_Barycentric);
//    vec3 a3 = smoothstep(vec3(0.0), d * wireframeWidth, fs_in.v_Barycentric);
    
//    float edgeFactor = min(min(a3.x, a3.y), a3.z);

//    // ==========================================
//    // 3. 混合光照颜色与线框
//    // ==========================================
//    vec3 finalColor = mix(wireframeColor, litColor, edgeFactor);

//    color = vec4(finalColor, 1.0f); 
//}