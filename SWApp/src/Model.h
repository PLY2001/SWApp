#pragma once
#include "Mesh.h"
#include <iostream>
#include "stb_image/stb_image.h"
#include "GL/glew.h"



class Model
{
private:
	glm::vec3 Pos;
	std::string directory;
	void processNode(aiNode* node, const aiScene* scene);
	Mesh processMesh(aiMesh* mesh, const aiScene* scene);
	std::vector<myTexture> loadMaterialTextures(aiMaterial* mat, aiTextureType type, std::string typeName);
	unsigned int TextureFromFile(const char* path, const std::string& directory);
	std::vector<myTexture> textures_loaded;
	
	

public:
	Model(std::string path,glm::vec3 Pos);
	Model() = default;
	void Draw(Shader& shader);
	void DrawInstanced(Shader& shader, int amount);
	glm::mat4 mModelMatrix;
	void SetPosition();
	void SetMatrix(float deltaTime);
	std::vector<Mesh> meshes;
};

class ModelMatrix
{
public:
	glm::mat4 Matrix = glm::mat4(1.0f);
	ModelMatrix(glm::vec3 Pos)
	{
		Matrix = glm::translate(Matrix, Pos);
	}
	
};