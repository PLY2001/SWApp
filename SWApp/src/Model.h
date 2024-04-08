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
	glm::mat4 mModelMatrix;
	

public:
	Model(std::string path);
	Model() = default;
	void Draw(Shader& shader);
	void DrawInstanced(Shader& shader, int amount);
	std::vector<Mesh> meshes;
	inline glm::mat4& GetModelMatrix() { return mModelMatrix; };
	void SetModelMatrixPosition(glm::vec3 Pos);
	void SetModelMatrixRotation(float Radians, glm::vec3 Axis);
	void SetModelMatrixScale(glm::vec3 Scale);
	float GetNormalizeScale(glm::vec3 MassCenter);
};