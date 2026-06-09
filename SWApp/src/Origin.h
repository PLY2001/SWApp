#pragma once
#include "Shader.h"
#include "VertexArray.h"
#include "VertexBuffer.h"

class Origin
{
public:
	Origin(Shader& shader);
	~Origin() = default;
	void Draw();
private:
	Shader m_shader;
	std::unique_ptr<VertexArray> m_va;
	std::unique_ptr<VertexBuffer> m_vb;
	unsigned int vaID;//VertexArray
	unsigned int vbID;

};

