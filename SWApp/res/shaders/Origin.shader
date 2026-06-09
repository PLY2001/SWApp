#shader vertex
#version 330 core 

layout(location=0) in vec3 position; 

layout(std140) uniform Matrices
{
	mat4 u_view;
	mat4 u_projection;
};

out VS_OUT{
	vec4 ModelPosition;
}vs_out;

void main() 
{ 
	vs_out.ModelPosition = vec4(position,1.0f);
	gl_Position = u_view*vec4(position,1.0f);
}

#shader geometry
#version 330 core 

layout(points) in;
layout(line_strip,max_vertices = 2) out;

layout(std140) uniform Matrices
{
	mat4 u_view;
	mat4 u_projection;
};

in VS_OUT{
	vec4 ModelPosition;
}gs_in[];

out GS_OUT{
	vec4 fColor;
}gs_out;

void main()
{
	gs_out.fColor = gs_in[0].ModelPosition;
	gl_Position=u_projection*u_view*vec4(0.0f,0.0f,0.0f,1.0f);
	EmitVertex();

	gl_Position=u_projection*gl_in[0].gl_Position;
	EmitVertex();

	EndPrimitive();
}


#shader fragment
#version 330 core 

in GS_OUT{
	vec4 fColor;
}fs_in;


out vec4 color; 

void main() 
{
	color = fs_in.fColor;
}