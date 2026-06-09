#include "Origin.h"


Origin::Origin(Shader& shader) :m_shader(shader)
{
	float Origin[] = { 50.0f,0.0f,0.0f,
					   0.0f,50.0f,0.0f,
					   0.0f,0.0f,50.0f };


	m_va.reset(new VertexArray(vaID));
	m_vb.reset(new VertexBuffer(vbID, Origin, 9 * sizeof(float)));

	VertexAttribLayout layout;//创建顶点属性布局实例
	layout.Push<GL_FLOAT>(3);//填入第一个属性布局，类型为float，每个点为3维向量

	m_va->AddBuffer(vbID, layout);//将所有属性布局应用于顶点缓冲区vb，并绑定在顶点数组对象va上

	m_va->Unbind();
	m_vb->Unbind();
}

void Origin::Draw()
{


	m_shader.Bind();
	m_va->Bind();

	glDrawArrays(GL_POINTS, 0, 3);

	m_shader.Unbind();
	m_va->Unbind();
}



