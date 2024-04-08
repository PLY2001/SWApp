// [Win32] Our example includes a copy of glfw3.lib pre-compiled with VS2010 to maximize ease of testing and compatibility with old VS compilers.
// To link with VS2010-era libraries, VS2015+ requires linking with legacy_stdio_definitions.lib, which we do using this pragma.
// Your own project should not be affected, as you are likely to link with a newer binary of GLFW that is adequate for your version of Visual Studio.
#if defined(_MSC_VER) && (_MSC_VER >= 1900) && !defined(IMGUI_DISABLE_WIN32_FUNCTIONS)
#pragma comment(lib, "legacy_stdio_definitions")
#endif
#include <GL/glew.h>
#include <GLFW/glfw3.h> // Will drag system OpenGL headers
#include "imgui.h"
#include "imgui_impl_glfw.h"
#include "imgui_impl_opengl3.h"
#include <stdio.h>
#define GL_SILENCE_DEPRECATION
#include "Application.h"
#include <windows.h>
#include "Application.h"

#include "Shader.h"
#include "Renderer.h"
#include "Model.h"
#include "UniformBuffer.h"
#include "InstanceBuffer.h"

MyApp::MyApplication& App = MyApp::MyApplication::GetInstance();//获取唯一的实例引用
std::unordered_map<std::string, MyApp::MyFaceFeature> faceMap;//获取面哈希表
std::map<MyApp::SWState, MyApp::MyState> swStateMap;//获取SW交互状态

enum class ViewDirection {
	FrontView, SideView, VerticalView
};//视图方向：前视图，侧视图，俯视图
ViewDirection viewDirction = ViewDirection::FrontView;//记录当前视图方向

enum class CullMode {
	CullBack, CullFront
};//剔除方法
CullMode cullMode = CullMode::CullFront;//记录当前剔除方法

float deltaTime = 0;//每次循环耗时
float lastTime = 0;//上一次记录时间

//窗口尺寸
unsigned int WinWidth = 600;
unsigned int WinHeight = 600;
float PictureSize = 50.0f; //正交投影取景范围大小

//照相机位置、前向、上向
glm::vec3 cameraPos[3] = { glm::vec3(0.0f, 0.0f, PictureSize + 1.0f),  glm::vec3(-PictureSize - 1.0f, 0.0f, 0.0f), glm::vec3(0.0f, PictureSize + 1.0f, 0.0f) };
glm::vec3 cameraFront[3] = { glm::vec3(0.0f, 0.0f, -1.0f), glm::vec3(1.0f, 0.0f, 0.0f), glm::vec3(0.0f, -1.0f, 0.0f) };
glm::vec3 cameraUp[3] = { glm::vec3(0.0f, 1.0f, 0.0f), glm::vec3(0.0f, 1.0f, 0.0f), glm::vec3(0.0f, 0.0f, -1.0f) };

bool modelLoaded = false;//是否导入了模型


// Main code
//int main(int, char**)
int WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow)
{
    //glfw初始化
    if (!glfwInit())
        return 1;
    const char* glsl_version = "#version 130";
    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 0);
    glfwWindowHint(GLFW_SAMPLES, 8);//设置MSAAx8
    glEnable(GL_MULTISAMPLE);//开启MSAA

    //创建窗口上下文
    GLFWwindow* window = glfwCreateWindow(WinWidth, WinHeight, "Display", nullptr, nullptr);
    if (window == nullptr) {
        glfwTerminate();
        return 1;
    }       
    glfwMakeContextCurrent(window);
    glfwSwapInterval(0); //1=开启垂直同步

    //glew初始化
	if (glewInit())
	{
		return 1;
	}
    

    //初始化ImGui
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO(); (void)io;
    io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard;     // Enable Keyboard Controls
    io.ConfigFlags |= ImGuiConfigFlags_NavEnableGamepad;      // Enable Gamepad Controls
    io.ConfigFlags |= ImGuiConfigFlags_DockingEnable;         // Enable Docking
    io.ConfigFlags |= ImGuiConfigFlags_ViewportsEnable;       // Enable Multi-Viewport / Platform Windows
    io.Fonts->AddFontFromFileTTF("res/fonts/msyh.ttc", 20.0f, nullptr, io.Fonts->GetGlyphRangesChineseFull());//中文字体
    // Setup Dear ImGui style
    ImGui::StyleColorsLight();
    // When viewports are enabled we tweak WindowRounding/WindowBg so platform windows can look identical to regular ones.
    ImGuiStyle& style = ImGui::GetStyle();
    if (io.ConfigFlags & ImGuiConfigFlags_ViewportsEnable) {
        style.WindowRounding = 0.0f;
        style.Colors[ImGuiCol_WindowBg].w = 1.0f;
    }
    // Setup Platform/Renderer backends
    ImGui_ImplGlfw_InitForOpenGL(window, true);
    ImGui_ImplOpenGL3_Init(glsl_version);

	//模型哈希表(毫米)
	std::unordered_map<std::string, Model> modelMap;

    //实例哈希表
    std::unordered_map<std::string, InstanceBuffer> instanceMap;

	//创建变换矩阵
    glm::mat4 modelMatrix;
	glm::mat4 viewMatrix;
	glm::mat4 projectionMatrix;
	
    //Shader
    Shader shader("res/shaders/Basic.shader");
	shader.Bind();
	shader.Unbind();

	//渲染方面的API
	Renderer renderer;

	//创建Uniform缓冲对象
	UniformBuffer ubo(2 * sizeof(glm::mat4), 0);
	std::vector<int> shaderIDs;
	shaderIDs.push_back(shader.RendererID);
    ubo.Bind(shaderIDs, "Matrices");

    //主循环
    while (!glfwWindowShouldClose(window))
    {
        //更新哈希表
        faceMap = App.GetFaceMap();
        swStateMap = App.GetSWStateMap();

        //模型、实例预处理
        if (swStateMap[MyApp::SWState::ModelLoaded] != MyApp::MyState::Succeed) {//重新读取文件时需要重新加载模型
            modelLoaded = false;
        }
        if (swStateMap[MyApp::SWState::ModelLoaded] == MyApp::MyState::Succeed && modelLoaded == false) {
            //加载模型
            float minScale = 1e10;
            float thisScale = 1e10;
            modelMap.clear();
			for (auto face : faceMap) {
				std::string fileName = face.first + ".STL";
                std::string filePath = App.GetExportPath();
                Model model((filePath + fileName));//读取文件
                thisScale = model.GetNormalizeScale(App.GetMassCenter());//求出每个面模型的缩放尺寸
                minScale = thisScale < minScale ? thisScale : minScale;//选择最小的缩放尺寸                               
				modelMap[face.first] = model;              
			}

			//创建实例
            instanceMap.clear();
			for (auto model : modelMap) {
                modelMap[model.first].SetModelMatrixScale(glm::vec3(minScale)); //缩放
                modelMap[model.first].SetModelMatrixPosition(-App.GetMassCenter()); //以质心置中 

				InstanceBuffer instance(sizeof(glm::mat4), &model.second.GetModelMatrix());
				instance.AddInstanceBuffermat4(model.second.meshes[0].vaID, 3);
				instanceMap[model.first] = instance;
			}
            modelLoaded = modelMap.size() > 0;            
                
        }

        //1.渲染模型	
		GLClearError();//清除错误信息

		//记录每帧的时间
		deltaTime = (float)glfwGetTime() - lastTime;
		lastTime = (float)glfwGetTime();

		//更新相机位置
		cameraPos[0] = glm::vec3(0.0f, 0.0f, PictureSize + 1.0f);
		cameraPos[1] = glm::vec3(-PictureSize - 1.0f, 0.0f, 0.0f);
		cameraPos[2] = glm::vec3(0.0f, PictureSize + 1.0f, 0.0f);

		//设置变换矩阵			
		//modelMatrix = glm::rotate(modelMatrix, deltaTime * glm::radians(50.0f), glm::vec3(0.0f, 1.0f, 0.0f));//旋转		
		viewMatrix = glm::lookAt(cameraPos[(int)viewDirction], cameraPos[(int)viewDirction] + cameraFront[(int)viewDirction], cameraUp[(int)viewDirction]);
		projectionMatrix = glm::ortho(-PictureSize, PictureSize, -PictureSize, PictureSize, 0.1f, PictureSize * 2.0f);

		//将model矩阵数组填入实例哈希表
        if (swStateMap[MyApp::SWState::ModelLoaded] == MyApp::MyState::Succeed) {
            for (auto instance : instanceMap) {
                //旋转
                //modelMap[instance.first].SetModelMatrixPosition(App.GetMassCenter());
                //modelMap[instance.first].SetModelMatrixRotation(deltaTime* glm::radians(50.0f), glm::vec3(0.0f, 1.0f, 0.0f));
                //modelMap[instance.first].SetModelMatrixPosition(-App.GetMassCenter());

                modelMatrix = modelMap[instance.first].GetModelMatrix();
                instance.second.SetDatamat4(sizeof(glm::mat4), &modelMatrix);
            }
        }
		//向uniform缓冲对象填入view、projection矩阵数据
		ubo.SetDatamat4(0, sizeof(glm::mat4), &viewMatrix);
		ubo.SetDatamat4(sizeof(glm::mat4), sizeof(glm::mat4), &projectionMatrix);

		//pass
		glEnable(GL_DEPTH_TEST);
		renderer.ClearColor(1.0f, 1.0f, 1.0f, 1.0f);
		renderer.ClearDepth();
		renderer.CullFace((int)cullMode);

		shader.Bind();
		if (swStateMap[MyApp::SWState::ModelLoaded] == MyApp::MyState::Succeed) {
			for (auto model : modelMap) {
				shader.SetUniform1f("type", (float)faceMap[model.first].AnnotationArray[0].Type / 255.0f);//获取面的MBD数据
				shader.SetUniform1f("isDatum", (float)faceMap[model.first].AnnotationArray[0].IsDatum);
				model.second.DrawInstanced(shader, 1);
			}
		}
		shader.Unbind();
		

        //2.渲染ImGui界面
        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();

        //MyApp		
		App.ShowMyApp();
        
        ImGui::Begin("Debug");
        //获取OpenGL错误信息	
		ImGui::Text(("OpenGL: " + std::to_string(GLCheckError())).c_str());
        //正交投影取景框大小
        ImGui::DragFloat("取景框大小", &PictureSize, 0.1f);
        //视图方向选择
        ImGui::RadioButton("正视图", (int*)&viewDirction, (int)ViewDirection::FrontView);
        ImGui::SameLine();
        ImGui::RadioButton("侧视图", (int*)&viewDirction, (int)ViewDirection::SideView);
        ImGui::SameLine();
        ImGui::RadioButton("俯视图", (int*)&viewDirction, (int)ViewDirection::VerticalView);
        //剔除模式选择
        ImGui::RadioButton("面正向剔除", (int*)&cullMode, (int)CullMode::CullFront);
		ImGui::SameLine();
        ImGui::RadioButton("面反向剔除", (int*)&cullMode, (int)CullMode::CullBack);
        ImGui::Text("allTime=%f", (float)App.allTime);
        ImGui::Text("feTime=%f", (float)App.feTime);
        ImGui::Text("aTime=%f", (float)App.aTime);
        ImGui::Text("fTime=%f", (float)App.fTime);
        ImGui::Text("swaTime=%f", (float)App.swaTime);
        ImGui::Text("bTime=%f", (float)App.bTime);
        ImGui::End();

		
        //Rendering       
        ImGuiIO& io = ImGui::GetIO();
        io.DisplaySize = ImVec2(WinWidth, WinHeight);
        ImGui::Render();
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
        if (io.ConfigFlags & ImGuiConfigFlags_ViewportsEnable)
        {
            GLFWwindow* backup_current_context = glfwGetCurrentContext();
            ImGui::UpdatePlatformWindows();
            ImGui::RenderPlatformWindowsDefault();
            glfwMakeContextCurrent(backup_current_context);
        }

        //3.一帧结束
        glfwPollEvents();
        glfwSwapBuffers(window);
    }

    //销毁
    ImGui_ImplOpenGL3_Shutdown();
    ImGui_ImplGlfw_Shutdown();
    ImGui::DestroyContext();

    glfwDestroyWindow(window);
    glfwTerminate();

    return 0;
}
