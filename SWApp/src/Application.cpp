#include "Application.h"
#include "imgui.h"




namespace MyApp {

	//必须使用CComPtr来定义智能指针，从而简化COM指针的操作，比如自动计数
	CComPtr<ISldWorks> swApp;// COM Pointer of Soldiworks object
	CComPtr<IModelDoc2> swDoc;// COM Pointer of Soldiworks Model Document
	CComPtr<IDispatch> swDispatch;//所有接口的父类(等效于C#的object)
	CComPtr<IConfiguration> swConfiguration;//用于获取DimXpertManager
	CComPtr<IDimXpertManager> swDimXpertManager;//管理DimXpert的一切数据
	CComPtr<IDimXpertPart> swDimXpertPart;//DimXpert零件
	CComPtr<IDimXpertFeature> swDimXpertFeature;//DimXpert特征
	CComPtr<IDimXpertAnnotation> swDimXpertAnnotation;//DimXpert标注
	VARIANT dimXpertAnnotationVT;//获取DimXpert标注的SAFEARRAY数组的载体
	VARIANT dimXpertFeatureVT;//获取DimXpert标注的SAFEARRAY数组的载体


	CComPtr<IFace2> swFace;//面
	VARIANT faceVT;//获取面的SAFEARRAY数组的载体
	//RIANT boxVT;//获取面的包围盒的SAFEARRAY数组的载体	
	//omPtr<IMathUtility> swMathUtility;//用于生成数学向量、矩阵等
	//omPtr<IMathPoint> startPoint;//投影光线起点，单位m
	//omPtr<IMathVector> projectDir;//投影光线方向
	//omPtr<IMathPoint> interactPoint;//投影光线与面的交点
	//RIANT startPointVT;//用于生成投影光线起点的SAFEARRAY数组的载体
	//RIANT projectDirVT;//用于生成投影光线方向的SAFEARRAY数组的载体
	//RIANT interactPointVT;//用于生成投影光线与面的交点的SAFEARRAY数组的载体
	CComPtr<IEntity> swEntity;//面的实体

	CComPtr<IModelDocExtension> swDocE;//swDoc的拓展版（需由swDoc来get），可获取一些新函数
	CComPtr<IAnnotation> swAnnotation;//sw的标注
	VARIANT swAnnotationVT;//获取sw的标注的SAFEARRAY数组的载体
	CComPtr<IEntity> SFSEntity;//面的实体
	VARIANT SFSEntityVT;//获取实体的SAFEARRAY数组的载体
	CComPtr<ISFSymbol> swSFSymbol;//表面粗糙度

	VARIANT swBodyVT;//获取"零件实体"的SAFEARRAY数组的载体
	CComPtr<IBody2> swBody;//零件实体

	CComPtr<IMassProperty2> swMassProperty;//质量属性
	VARIANT massCenterVT;//获取质心的SAFEARRAY数组的载体

	HRESULT result = NOERROR; //存储函数的输出结果
	
	//CComBSTR _messageToUser;// COM Style String for message to user
	//long _lMessageResult;// long type variable to store the result value by user

	void MyApplication::ShowMyApp()
    {
		EnableDocking(); //开启Docking特性
		//ShowImguiExample();
		//ImGui::ShowDemoWindow();

        ImGui::Begin("SolidWorks API");
        ImGui::Text("%.3f ms/frame (%.1f FPS)", 1000.0f / ImGui::GetIO().Framerate, ImGui::GetIO().Framerate);
		
		//文件路径
		ImGui::InputText(".SLDPRT", InputName, 64);

		//连接SW按钮
		if (ImGui::Button("连接SW")) {			
			myState = ConnectSW() ? MyState::Succeed : MyState::Failed;
			SWStateMap[SWState::Connected] = myState;
			//ImGui::OpenPopup("提示");
		}
		ImGui::SameLine();
		ImGui::Text(MyStateMessage[(int)SWStateMap[SWState::Connected]].c_str());

		//打开文件按钮
		if (ImGui::Button("打开文件")) {
			SWStateMap[SWState::PropertyGot] = MyState::Nothing;
			SWStateMap[SWState::MassPropertyGot] = MyState::Nothing;
			SWStateMap[SWState::MBDGot] = MyState::Nothing;
			SWStateMap[SWState::ModelLoaded] = MyState::Nothing;			
			if (SWStateMap[SWState::Connected] == MyState::Succeed) {
				CADName = InputName;
				myState = OpenFile() ? MyState::Succeed : MyState::Failed;
				SWStateMap[SWState::FileOpen] = myState;
			}
			else {
				myState = MyState::Nothing;
				SWStateMap[SWState::FileOpen] = myState;
			}
			//ImGui::OpenPopup("提示");
		}
		ImGui::SameLine();
		ImGui::Text(MyStateMessage[(int)SWStateMap[SWState::FileOpen]].c_str());

		//读取属性按钮
		if (ImGui::Button("读取文档属性")) {
			if ((int)SWStateMap[SWState::Connected] * (int)SWStateMap[SWState::FileOpen] == 1) {
				myState = ReadProperty() ? MyState::Succeed : MyState::Failed;
				SWStateMap[SWState::PropertyGot] = myState;
			}
			else
			{
				myState = MyState::Nothing;
				SWStateMap[SWState::PropertyGot] = myState;
			}
			//ImGui::OpenPopup("提示");
		}
		ImGui::SameLine();
		ImGui::Text(MyStateMessage[(int)SWStateMap[SWState::PropertyGot]].c_str());

		//加载质量属性按钮
		if (ImGui::Button("加载质量属性")) {
			if ((int)SWStateMap[SWState::Connected] * (int)SWStateMap[SWState::FileOpen] == 1) {
				myState = ReadMassProperty() ? MyState::Succeed : MyState::Failed;
				SWStateMap[SWState::MassPropertyGot] = myState;
			}
			else
			{
				myState = MyState::Nothing;
				SWStateMap[SWState::MassPropertyGot] = myState;
			}
			//ImGui::OpenPopup("提示");
		}
		ImGui::SameLine();
		ImGui::Text(MyStateMessage[(int)SWStateMap[SWState::MassPropertyGot]].c_str());

		//读取MBD特征及其标注按钮
		if (ImGui::Button("读取MBD特征及其标注")) {
			if ((int)SWStateMap[SWState::Connected] * (int)SWStateMap[SWState::FileOpen] == 1) {
				myState = ReadMBD() ? MyState::Succeed : MyState::Failed;
				SWStateMap[SWState::MBDGot] = myState;
			}
			else
			{
				myState = MyState::Nothing;
				SWStateMap[SWState::MBDGot] = myState;
			}
			//ImGui::OpenPopup("提示");
		}
		ImGui::SameLine();
		//选择是否在读取MBD时导出模型
		ImGui::Checkbox("导出?", &toSave);
		ImGui::SameLine();
		ImGui::Text(MyStateMessage[(int)SWStateMap[SWState::MBDGot]].c_str());

		

		//加载模型按钮
		if (ImGui::Button("加载模型并显示")) {
			if ((int)SWStateMap[SWState::Connected] * (int)SWStateMap[SWState::FileOpen] * (int)SWStateMap[SWState::MassPropertyGot] * (int)SWStateMap[SWState::MBDGot] == 1) {
				myState = LoadModel() ? MyState::Succeed : MyState::Failed;
				SWStateMap[SWState::ModelLoaded] = myState;
			}
			else
			{
				myState = MyState::Nothing;
				SWStateMap[SWState::ModelLoaded] = myState;
			}
			//ImGui::OpenPopup("提示");
		}
		ImGui::SameLine();
		ImGui::Text(MyStateMessage[(int)SWStateMap[SWState::ModelLoaded]].c_str());

		

		//显示弹窗
		//ShowMessage(MyStateMessage[(int)myState].c_str());
		
		//显示文档属性
		if (SWStateMap[SWState::PropertyGot] == MyState::Succeed) {
			if (ImGui::CollapsingHeader("文档属性")) {
				if (ImGui::TreeNode("自定义属性")){
					for (auto p : property) {
						std::string m = p.first + ":";
						m = m + p.second;
						ImGui::Text(m.c_str());
					}
					ImGui::TreePop();
					ImGui::Separator();
				}
				if (ImGui::TreeNode("摘要")) {
					for (auto s : summary) {
						std::string m = s.first + s.second;
						ImGui::Text(m.c_str());
					}
					ImGui::TreePop();
					ImGui::Separator();
				}
			}
		}
		
		//显示质量属性
		if (SWStateMap[SWState::MassPropertyGot] == MyState::Succeed) {
			if (ImGui::CollapsingHeader("质量属性")) {
				if (ImGui::TreeNode("质心(毫米)")){
					ImGui::Text("X = %f",MassCenter.x);
					ImGui::Text("Y = %f",MassCenter.y);
					ImGui::Text("Z = %f",MassCenter.z);
					ImGui::TreePop();
					ImGui::Separator();
				}
				
			}
		}

		//显示MBD
		if (SWStateMap[SWState::MBDGot] == MyState::Succeed) {
			if (ImGui::CollapsingHeader("MBD特征及其标注")){					
				ImGui::Text("MBD特征总数:%d", DimXpertFeatureCount);
				ImGui::Text("MBD标注总数:%d", DimXpertAnnotationCount);
				ImGui::Separator();
				for (auto feature : FaceMap) {
					if (ImGui::TreeNode(feature.second.Name.c_str())) {
						for (auto annotation : feature.second.AnnotationArray) {
							ImGui::Text(annotation.Name.c_str());
							ImGui::BulletText("标注类型:%i",annotation.Type);
							if (annotation.Type != swDimXpertDatum) {
								ImGui::BulletText("标注公差大小:%f", annotation.AccuracySize);
								ImGui::BulletText("标注公差等级:%d", annotation.AccuracyLevel);
								for (auto datum : annotation.ToleranceDatumNames) {
									ImGui::BulletText(("标注公差基准:" + datum).c_str());
								}
								if (annotation.MCMType != swDimXpertMaterialConditionModifier_unknown) {
									ImGui::BulletText("材料实体状态:%i", annotation.MCMType);
								}
							}							
						}
						ImGui::TreePop();
						ImGui::Separator();
					}

				}
			}
		}
		
        ImGui::End();

    }





    void  MyApplication::EnableDocking()
    {
        
        static bool opt_fullscreen = false;//false时可关闭ImGui背景
        static bool opt_padding = false;
        static ImGuiDockNodeFlags dockspace_flags = ImGuiDockNodeFlags_None;

        // We are using the ImGuiWindowFlags_NoDocking flag to make the parent window not dockable into,
        // because it would be confusing to have two docking targets within each others.
        ImGuiWindowFlags window_flags = ImGuiWindowFlags_MenuBar | ImGuiWindowFlags_NoDocking;
        if (opt_fullscreen)
        {
            const ImGuiViewport* viewport = ImGui::GetMainViewport();
            ImGui::SetNextWindowPos(viewport->WorkPos);
            ImGui::SetNextWindowSize(viewport->WorkSize);
            ImGui::SetNextWindowViewport(viewport->ID);
            ImGui::PushStyleVar(ImGuiStyleVar_WindowRounding, 0.0f);
            ImGui::PushStyleVar(ImGuiStyleVar_WindowBorderSize, 0.0f);
            window_flags |= ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoCollapse | ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoMove;
            window_flags |= ImGuiWindowFlags_NoBringToFrontOnFocus | ImGuiWindowFlags_NoNavFocus;
        }
        else
        {
            dockspace_flags &= ~ImGuiDockNodeFlags_PassthruCentralNode;
        }

        // When using ImGuiDockNodeFlags_PassthruCentralNode, DockSpace() will render our background
        // and handle the pass-thru hole, so we ask Begin() to not render a background.
        if (dockspace_flags & ImGuiDockNodeFlags_PassthruCentralNode)
            window_flags |= ImGuiWindowFlags_NoBackground;

        // Important: note that we proceed even if Begin() returns false (aka window is collapsed).
        // This is because we want to keep our DockSpace() active. If a DockSpace() is inactive,
        // all active windows docked into it will lose their parent and become undocked.
        // We cannot preserve the docking relationship between an active window and an inactive docking, otherwise
        // any change of dockspace/settings would lead to windows being stuck in limbo and never being visible.
        if (!opt_padding)
            ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(0.0f, 0.0f));
        ImGui::Begin("SWApp", nullptr, window_flags);
        if (!opt_padding)
            ImGui::PopStyleVar();

        if (opt_fullscreen)
            ImGui::PopStyleVar(2);

        // Submit the DockSpace
        ImGuiIO& io = ImGui::GetIO();
        if (io.ConfigFlags & ImGuiConfigFlags_DockingEnable)
        {
            ImGuiID dockspace_id = ImGui::GetID("MyDockSpace");
            ImGui::DockSpace(dockspace_id, ImVec2(0.0f, 0.0f), dockspace_flags);
        }
        
		
		ShowMenuBar();
		

        ImGui::End();
    }


	void  MyApplication::ShowMenuBar()
	{
		
		if (ImGui::BeginMenuBar()) {
			if (ImGui::BeginMenu(" 关于 ")) {
				if (ImGui::MenuItem("项目地址")) {
					toLoad = true;
				}

				ImGui::EndMenu();

			}
			ImGui::EndMenuBar();
		}


		if (toLoad)
		{
			ImGui::OpenPopup("提示");
			toLoad = ShowMessage("github.com/PLY2001/SWApp");
		}
	}

	void  MyApplication::ShowImguiExample()
	{
		static float f = 0.0f;
		static int counter = 0;
		static bool show_demo_window = true;
		static bool show_another_window = true;
		static ImVec4 clear_color = ImVec4(0, 0, 0, 0);

		ImGui::Begin("Example");                          // Create a window called "Hello, world!" and append into it.



		
		ImGui::Text("This is some useful text.");               // Display some text (you can use a format strings too)
		ImGui::Checkbox("Demo Window", &show_demo_window);      // Edit bools storing our window open/close state
		ImGui::Checkbox("Another Window", &show_another_window);

		ImGui::SliderFloat("float", &f, 0.0f, 1.0f);            // Edit 1 float using a slider from 0.0f to 1.0f
		ImGui::ColorEdit3("clear color", (float*)&clear_color); // Edit 3 floats representing a color

		if (ImGui::Button("Button"))                            // Buttons return true when clicked (most widgets return true when edited/activated)
			counter++;
		ImGui::SameLine();
		ImGui::Text("counter = %d", counter);
		
		ImGui::End();
	}

	bool  MyApplication::ShowMessage(const char* message)
	{
		
		// Always center this window when appearing
		ImVec2 center = ImGui::GetMainViewport()->GetCenter();
		ImGui::SetNextWindowPos(center, ImGuiCond_Appearing, ImVec2(0.5f, 0.5f));

		if (ImGui::BeginPopupModal("提示", NULL, ImGuiWindowFlags_AlwaysAutoResize))
		{


			ImGui::Text(message);

			ImGui::Separator();


			if (ImGui::Button("关闭", ImVec2(120, 0)))
			{

				ImGui::CloseCurrentPopup();
				ImGui::EndPopup();
				return false;

			}
			ImGui::EndPopup();
		}
		return true;
	}
	

			

	

	bool MyApplication::ConnectSW()
	{
		CoInitialize(NULL); //初始化COM库（让Windows加载DLLs）
		//CoInitializeEx(0, COINIT_MULTITHREADED); //初始化COM库（让Windows加载DLLs）（多线程版）
		swApp.Release();//Realease的作用是避免重复初始化swApp，导致出错
		if (swApp.CoCreateInstance(__uuidof(SldWorks), NULL, CLSCTX_LOCAL_SERVER) != S_OK)//创建swApp指针的对象实例
		{
			// Stop COM 
			CoUninitialize();
			return false;
		}
		return true;
	}

	bool MyApplication::OpenFile()
	{
		//当已经打开过文件时，先关掉现有文件
		if (SWStateMap[SWState::FileOpen] == MyState::Succeed) { 
			VARIANT_BOOL allClosed;
			result = swApp->CloseAllDocuments(VARIANT_TRUE, &allClosed);
		}

		// Open Selected file             
		CComBSTR fileName = (CADPath + CADName + CADType).c_str();
		long error = NOERROR;
		long warning = NOERROR;

		//打开文件
		swDoc.Release();
		result = swApp->OpenDoc6(fileName, (int)swDocumentTypes_e::swDocPART, (int)swOpenDocOptions_e::swOpenDocOptions_Silent, nullptr, &error, &warning, &swDoc);//error=2表示无法找到文件

		if (result!=S_OK || error != NOERROR) {
			CoUninitialize();
			return false;
		}
		swApp->put_Visible(VARIANT_TRUE);

		//获取更高级的doc
		swDocE.Release();
		result = swDoc->get_Extension(&swDocE);
		if (result != S_OK) {
			CoUninitialize();
			return false;
		}

		return true;
	}

	bool MyApplication::ReadProperty()
	{
		CComBSTR customFieldNames[2] = { "Description" ,"Weight" };//设置需读取的自定义属性
		for (CComBSTR fieldName : customFieldNames) {
			CComBSTR fieldResult;
			result = swDoc->get_CustomInfo(fieldName, &fieldResult);
			if (result != S_OK) {
				CoUninitialize();
				return false;
			}
			std::string aaa = GbkToUtf8(_com_util::ConvertBSTRToString(fieldName));
			std::string bbb = GbkToUtf8(_com_util::ConvertBSTRToString(fieldResult));
			property[aaa] = bbb;
		}

		//设置需读取的摘要
		std::unordered_map<swSummInfoField_e, std::string> summaryFieldNames = {
			 {swSummInfoField_e::swSumInfoAuthor,"Author:"}
			,{swSummInfoField_e::swSumInfoComment,"Comment:"}
			,{swSummInfoField_e::swSumInfoCreateDate,"CreateDate:"}
			,{swSummInfoField_e::swSumInfoCreateDate2,"CreateDate2:"}
			,{swSummInfoField_e::swSumInfoKeywords,"Keywords:"}
			,{swSummInfoField_e::swSumInfoSaveDate,"SaveDate:"}
			,{swSummInfoField_e::swSumInfoSaveDate2,"SaveDate2:"}
			,{swSummInfoField_e::swSumInfoSavedBy,"SavedBy:"}
			,{swSummInfoField_e::swSumInfoSubject,"Subject:"}
			,{swSummInfoField_e::swSumInfoTitle,"Title:" }
		};
		for (auto fieldName : summaryFieldNames) {
			CComBSTR fieldResult;
			result = swDoc->get_SummaryInfo(fieldName.first, &fieldResult);
			if (result != S_OK) {
				CoUninitialize();
				return false;
			}
			std::string bbb = GbkToUtf8(_com_util::ConvertBSTRToString(fieldResult));
			summary[fieldName.second] = bbb;
		}

		return true;

		

	}

	bool MyApplication::ReadMBD()
	{
		long allStartTime = GetTickCount();
		//首先新建以该CAD文件命名的文件夹，供后续保存模型用
		if (toSave) {
			bool flag = CreateDirectory((CADPath + CADName).c_str(), NULL);
		}

		//步骤：swDoc->swConfiguration->swDimXpertManager->swDimXpertPart->Feature->Annotation
		FaceMap.clear();//清空面哈希表
		swConfiguration.Release();
		result = swDoc->IGetActiveConfiguration(&swConfiguration);//获取swConfiguration
		if (result != S_OK) {
			CoUninitialize();
			return false;
		}
		swDimXpertManager.Release();
		result = swConfiguration->get_DimXpertManager(VARIANT_TRUE, &swDimXpertManager);//获取swDimXpertManager
		if (result != S_OK) {
			CoUninitialize();			
			return false;
		}
		swDispatch.Release();
		result = swDimXpertManager->get_DimXpertPart(&swDispatch);//获取swDimXpertPart(由swDispatch父类接口实例承载)
		if (result != S_OK) {
			CoUninitialize();			
			return false;
		}
		swDimXpertPart = swDispatch;//转化为具体接口类型
		//result = swDimXpertPart->GetFeatureCount(&DimXpertFeatureCount);//获取特征数量（*过时*）（由于模型存在一些奇怪的没有注解的不明特征）
		//if (result != S_OK) {
		//	CoUninitialize();
		//	return false;
		//}
		result = swDimXpertPart->GetAnnotationCount(&DimXpertAnnotationCount);//读取标注数量
		if (result != S_OK) {
			CoUninitialize();			
			return false;
		}
		
		//1.获取特征SAFEARRAY数组的承载体
		swDimXpertPart->GetFeatures(&dimXpertFeatureVT);
		if (result != S_OK) {
			CoUninitialize();			
			return false;
		}		
		//读取DimXpert特征的SAFEARRAY
		LPVOID feData = nullptr;//接收读取后的数组
		LONG featureCount;//接收读取后的数组大小
		if (!ReadSafeArray(&dimXpertFeatureVT, VT_DISPATCH, 1, &feData, &featureCount)) {
			CoUninitialize();
			return false;
		}
		IDispatch** myfeData = (IDispatch**)feData;//将数组指针赋与IDispatch**类型的指针数组的指针，与ReadSafeArray类型一致
		IDimXpertFeature* myFeatureData;//用于最终获取IDimXpertFeature*类型数据						
		CComBSTR dimXpertFeatureName;
		CComBSTR dimXpertAnnotationName;
		std::string dimXpertFeatureNameStr;
		std::string dimXpertAnnotationNameStr;

		long feStartTime = GetTickCount();
		aTime = 0;
		fTime = 0;

		
		//std::thread th[50];
		//MyApplicationAdapter maa(this);
		//for (int i = 0; i < featureCount; i++) {
		//	
		//	th[i] = std::thread(maa, i, std::ref(myfeData));
		//}
		//for (int i = 0; i < featureCount; i++)
		//	th[i].join();
		
		for (int feIndex = 0; feIndex < featureCount; feIndex++) { //9991ms
			result = myfeData[feIndex]->QueryInterface(IID_IDimXpertFeature, (void**)&myFeatureData);//为了将IDispatch*类型转为IDimXpertFeature*，需要用QueryInterface查询是否可转换(CComPtr类型直接=即可)，IID_IDimXpertFeature是要查询的接口类型
			if (result != S_OK) {
				CoUninitialize();										
				return false;
			}			
			swDimXpertFeature = CComPtr<IDimXpertFeature>(myFeatureData);//用构造函数将IDimXpertFeature*普通指针转为CComPtr智能指针			
			
			//a.获取特征名称
			result = swDimXpertFeature->get_Name(&dimXpertFeatureName);//result为false？不知为何，但是能读取
			//if (result != S_OK) {
			//	CoUninitialize();										
			//	return false;
			//}
			dimXpertFeatureNameStr = GbkToUtf8(_com_util::ConvertBSTRToString(dimXpertFeatureName));//BSTR转String(Gbk)(Imgui会乱码)，再转String(Utf8)			

			//存入特征面数组
			MyFaceFeature faceFeature;
			faceFeature.Name = dimXpertFeatureNameStr;

			//2.获取标注SAFEARRAY数组的承载体
			result = swDimXpertFeature->GetAppliedAnnotations(&dimXpertAnnotationVT);
			if (result != S_OK) {
				CoUninitialize();										
				return false;
			}
			//读取DimXpert标注的SAFEARRAY
			LPVOID aData = nullptr;//接收读取后的数组
			LONG annotationCount;//接收读取后的数组大小
			if (!ReadSafeArray(&dimXpertAnnotationVT, VT_DISPATCH, 1, &aData, &annotationCount)) {
				//CoUninitialize();
				//return false;
				continue;//有时dimXpertAnnotationVT是空的
			}
			if (aData == nullptr) {
				continue;//Realease模式下ReadSafeArray判断一直失误，不明原因
			}
			faceFeature.AnnotationCount = annotationCount;
			IDispatch** myaData = (IDispatch**)aData;//将数组指针赋与IDispatch**类型的指针数组的指针，与ReadSafeArray类型一致
			
			long aStartTime = GetTickCount();
			//std::thread th[50];
			//MyApplicationAdapter maa(this);
			//for (int i = 0; i < annotationCount; i++) {
			//
			//	th[i] = std::thread(maa, i, std::ref(myaData), std::ref(faceFeature));
			//}
			//for (int i = 0; i < annotationCount; i++)
			//	th[i].join();

			IDimXpertAnnotation* myAnnotationData;//用于获取IDimXpertAnnotation*类型数据
			
			for (int aIndex = 0; aIndex < annotationCount; aIndex++) { //243ms
				result = myaData[aIndex]->QueryInterface(IID_IDimXpertAnnotation, (void**)&myAnnotationData);//为了将IDispatch*类型转为IDimXpertAnnotation*，需要用QueryInterface查询是否可转换(CComPtr类型直接=即可)，IID_IDimXpertAnnotation是要查询的接口类型
				if (result != S_OK) {
					CoUninitialize();
					return false;
				}
				swDimXpertAnnotation = CComPtr<IDimXpertAnnotation>(myAnnotationData);//用构造函数将IDimXpertAnnotation*普通指针转为CComPtr智能指针
				
				//a.获取标注名称
				result = swDimXpertAnnotation->get_Name(&dimXpertAnnotationName);
				//if (result != S_OK) {
				//	CoUninitialize();										
				//	return false;
				//}
				dimXpertAnnotationNameStr = GbkToUtf8(_com_util::ConvertBSTRToString(dimXpertAnnotationName));
				
				//b.获取标注类型
				swDimXpertAnnotationType_e dimXpertAnnotationType;
				result = swDimXpertAnnotation->get_Type(&dimXpertAnnotationType);
				if (result != S_OK) {
					CoUninitialize();
					return false;
				}
				
				//c.获取公差
				double toleranceSize = 0;
				int toleranceLevel = 0;
				std::string datumName;
				std::vector<std::string> toleranceDatumNames;
				swDimXpertMaterialConditionModifier_e MCMType = swDimXpertMaterialConditionModifier_unknown;
				ReadAnnotationData(dimXpertAnnotationType, &toleranceSize, &toleranceLevel, &datumName, toleranceDatumNames,&MCMType);//可以返回公差等级（1.轴/孔 2.线性尺寸 3.形位公差 三者等级定义不同）
			
				//存入特征面数组的标注数组
				MyAnnotation myAnnotation;
				myAnnotation.Name = dimXpertAnnotationNameStr;
				myAnnotation.Type = dimXpertAnnotationType;	
				myAnnotation.IsTolerance = dimXpertAnnotationType != swDimXpertDatum ? 1 : 0;
				myAnnotation.AccuracySize = toleranceSize;
				myAnnotation.AccuracyLevel = toleranceLevel;
				myAnnotation.IsDatum = dimXpertAnnotationType == swDimXpertDatum ? 1 : 0;
				myAnnotation.DatumName = datumName;
				myAnnotation.ToleranceDatumNames = toleranceDatumNames;
				myAnnotation.hasMCM = MCMType != swDimXpertMaterialConditionModifier_unknown ? 1 : 0;
				myAnnotation.MCMType = MCMType;
				faceFeature.AnnotationArray.push_back(myAnnotation);
			
			}
			long aEndTime = GetTickCount();
			aTime += ((aEndTime - aStartTime));
			//3.读取DimXpert特征所对应的面并保存为文件

			//a.设定当前面的名称
			CComBSTR faceName = "";
			std::string fileIndex = std::to_string(feIndex);//int转string
			result = faceName.Append(fileIndex.c_str());
			result = faceName.Append("_");
			result = faceName.Append(dimXpertFeatureName);

			//b.读取DimXpert特征所对应的面
			result = swDimXpertFeature->GetFaces(&faceVT);
			//读取面的SAFEARRAY
			LPVOID fData = nullptr;
			LONG faceCount;
			if (!ReadSafeArray(&faceVT, VT_DISPATCH, 1, &fData, &faceCount)) {
				CoUninitialize();
				return false;
			}
			IDispatch** myfData = (IDispatch**)fData;
			IFace2* myFaceData;//用于获取IFace2*类型数据			
			long fStartTime = GetTickCount();
			for (int fIndex = 0; fIndex < faceCount; fIndex++) { //15ms
				result = myfData[fIndex]->QueryInterface(IID_IFace2, (void**)&myFaceData);
				if (result != S_OK) {
					CoUninitialize();
					return false;
				}				
				swFace = CComPtr<IFace2>(myFaceData);
				swEntity = swFace;
				swEntity->put_ModelName(faceName);//设置模型名

				//b.使SW自动选择当前特征对应的面
				VARIANT_BOOL isSelected;
				if (fIndex > 0) {
					swEntity->Select4(VARIANT_TRUE, nullptr, &isSelected);
				}
				else {
					swEntity->Select4(VARIANT_FALSE, nullptr, &isSelected);
				}


				//在包围盒范围内向面投影光线 求交点，100个点需要20多秒，太慢了
				//myFaceData->GetBox(&boxVT);//获取包围盒坐标。一共6个值：第一个点的xyz，第二个点的xyz，单位m
				////读取包围盒的SAFEARRAY
				//LPVOID bData = nullptr;
				//LONG boxCount;
				//if (!ReadSafeArray(&boxVT, VT_R8, 1, &bData, &boxCount)) {
				//	CoUninitialize();
				//	return false;
				//}
				//// here you can cast pData to an array (pointer) of the type you expect
				//double* mybData = (double*)bData;
				//// use the data here.
				//double myBoxPos1[3] = { 0,0,0 };//用于获取double类型数据	
				//double myBoxPos2[3] = { 0,0,0 };//用于获取double类型数据	
				//for (int i = 0; i < boxCount; i++) {
				//	if (i < 3)
				//		myBoxPos1[i] = mybData[i];//包围盒点1
				//	else
				//		myBoxPos2[i - 3] = mybData[i];//包围盒点2
				//}
				//
				//double thisPos[3];//目前的投影光线起点
				//double dir[3] = { 1,0,0 };//目前的投影光线方向
				//int sampleCount = 10;//投影采样次数
				//for (int i = 0; i < sampleCount; i++) {
				//	thisPos[0] = myBoxPos1[0] + i * (myBoxPos2[0] - myBoxPos1[0]) / sampleCount;
				//	thisPos[1] = myBoxPos1[1] + i * (myBoxPos2[1] - myBoxPos1[1]) / sampleCount;
				//	thisPos[2] = myBoxPos1[2] + i * (myBoxPos2[2] - myBoxPos1[2]) / sampleCount;
				//
				//	startPoint.Release();
				//	projectDir.Release();
				//	interactPoint.Release();
				//
				//	CreatVARIANTArray(3, VT_R8, thisPos, &startPointVT);//生成VARIANT数组
				//	swDispatch.Release();
				//	result = swMathUtility->CreatePoint(startPointVT, &swDispatch);//生成点
				//	startPoint = swDispatch;
				//
				//	CreatVARIANTArray(3, VT_R8, dir, &projectDirVT);//生成VARIANT数组
				//	swDispatch.Release();
				//	result = swMathUtility->CreateVector(projectDirVT, &swDispatch);//生成向量
				//	projectDir = swDispatch;
				//
				//	result = swFace->GetProjectedPointOn(startPoint, projectDir, &interactPoint);//投影，求得的交点单位是m，若未相交为NULL
				//	if (interactPoint != NULL) {
				//		result = interactPoint->get_ArrayData(&interactPointVT);
				//		LPVOID iData = nullptr;
				//		LONG iCount;
				//		if (ReadSafeArray(&interactPointVT, VT_R8, 1, &iData, &iCount)) {
				//			//存数据
				//		}
				//
				//	}
				//
				//}

			
			}
			long fEndTime = GetTickCount();
			fTime += ((fEndTime - fStartTime));

			//c.以面命名将特征存入面哈希表							
			//VARIANT_BOOL isSetName = VARIANT_FALSE;
			//swDoc->SelectedFaceProperties(0, 0, 0, 0, 0, 0, 0, VARIANT_TRUE, faceName,&isSetName);//设置面属性的名字（sw右键面属性可见）
			std::string FaceName = GbkToUtf8(_com_util::ConvertBSTRToString(faceName));
			FaceMap[FaceName] = faceFeature;
			//FaceMap[FaceName].AppliedFaceNameBSTR = faceName.Copy();//给特征存储所属面的BSTR名(因为string转回BSTR有乱码)

			//d.保存面为stl文件（当有选中的面时，直接保存时默认保存该面）
			if (toSave) {
				long error = NOERROR;
				long warning = NOERROR;
				VARIANT_BOOL isSaved;
				result = faceName.Append(".STL");
				CComBSTR savePath = (CADPath + CADName + "\\").c_str();
				result = savePath.Append(faceName);
				result = swApp->SetUserPreferenceToggle(swUserPreferenceToggle_e::swSTLDontTranslateToPositive, VARIANT_TRUE);//设置sw导出stl时不正向化坐标系（保留建模的坐标系）
				if (result != S_OK) {
					CoUninitialize();
					return false;
				}
				result = swDoc->SaveAs4(savePath, swSaveAsCurrentVersion, swSaveAsOptions_Silent, &error, &warning, &isSaved);//保存文件
				if (result != S_OK) {
					CoUninitialize();
					return false;
				}
			}
			
			
			
		}
		
		long feEndTime = GetTickCount();
		feTime = feEndTime - feStartTime;
		

		//4.获取表面粗糙度		
		result = swDocE->GetAnnotations(&swAnnotationVT);
		if (result != S_OK) {
			CoUninitialize();
			return false;
		}

		//读取SW标注的SAFEARRAY
		LPVOID swaData = nullptr;
		LONG swaCount;
		if (!ReadSafeArray(&swAnnotationVT, VT_DISPATCH, 1, &swaData, &swaCount)) {
			CoUninitialize();
			return false;
		}
		IDispatch** myswaData = (IDispatch**)swaData;
		IAnnotation* myswAnnotationsData;//用于获取IAnnotation*类型数据
		long swaStartTime = GetTickCount();
		for (int swaIndex = 0; swaIndex < swaCount; swaIndex++) { //188ms
			result = myswaData[swaIndex]->QueryInterface(IID_IAnnotation, (void**)&myswAnnotationsData);
			if (result != S_OK) {
				CoUninitialize();
				return false;
			}
			swAnnotation = CComPtr<IAnnotation>(myswAnnotationsData);

			//a.判断当前标注是否是表面粗糙度
			long swAnnotationType;
			result = swAnnotation->GetType(&swAnnotationType);
			if (result != S_OK) {
				CoUninitialize();
				return false;
			}
			if (swAnnotationType == swAnnotationType_e::swSFSymbol) {//是否是粗糙度标注
				long entityType;
				swDispatch.Release();
				result = swAnnotation->IGetAttachedEntityTypes(&entityType);
				if (result != S_OK) {
					CoUninitialize();
					return false;
				}
				if (entityType == swSelectType_e::swSelFACES) {//实体是否是面
					result = swAnnotation->GetAttachedEntities(&SFSEntityVT);
					if (result != S_OK) {
						CoUninitialize();
						return false;
					}
					//读取entity的SAFEARRAY
					LPVOID eData = nullptr;
					LONG eCount;
					if (!ReadSafeArray(&SFSEntityVT, VT_DISPATCH, 1, &eData, &eCount)) {
						CoUninitialize();
						return false;
					}
					IDispatch** myeData = (IDispatch**)eData;
					IEntity* myEntityData;//用于获取IEntity*类型数据
					for (int eIndex = 0; eIndex < eCount; eIndex++) {
						result = myeData[eIndex]->QueryInterface(IID_IEntity, (void**)&myEntityData);
						if (result != S_OK) {
							CoUninitialize();
							return false;
						}
						SFSEntity = CComPtr<IEntity>(myEntityData);

						//b.获取该表面粗糙度所属的面
						CComBSTR entityName;
						result = SFSEntity->get_ModelName(&entityName);
						if (result != S_OK) {
							CoUninitialize();
							return false;
						}
						std::string faceName = GbkToUtf8(_com_util::ConvertBSTRToString(entityName));
						
						//c.获取该表面粗糙度的数据
						result = swAnnotation->GetSpecificAnnotation(&swDispatch);//获取特定标注
						if (result != S_OK) {
							CoUninitialize();
							return false;
						}
						swSFSymbol = swDispatch;//特定标注转化为表面粗糙度
						long SFSymbolType;//swSFSymType_e
						result = swSFSymbol->GetSymbol(&SFSymbolType);
						if (result != S_OK) {
							CoUninitialize();
							return false;
						}
						CComBSTR text;
						result = swSFSymbol->GetTextAtIndex(0, &text);//获取第一个文本
						if (result != S_OK) {
							CoUninitialize();
							return false;
						}
						std::string textstr = GbkToUtf8(_com_util::ConvertBSTRToString(text));
						double SFSymbolSize = ReadDoubleFromString(textstr);//获取粗糙度数值

						//d.添加至所属的面特征中
						if (FaceMap.count(faceName) > 0) {
							MyAnnotation SFSAnnotation;
							SFSAnnotation.IsSFSymbol = 1;
							SFSAnnotation.Name = "粗糙度" + textstr;
							SFSAnnotation.AccuracySize = SFSymbolSize;
							SFSAnnotation.AccuracyLevel = 1;
							SFSAnnotation.SFSType = (swSFSymType_e)SFSymbolType;
							FaceMap[faceName].AnnotationArray.push_back(SFSAnnotation);
							FaceMap[faceName].AnnotationCount++;
							DimXpertAnnotationCount++;
						}
						
						


					}
				}
			}
			
		}
		long swaEndTime = GetTickCount();
		swaTime = swaEndTime - swaStartTime;
		
		//5.导出无MBD标注的面
		bool hasNoMBDFace = false;//记录该类面是否存在

		CComPtr<IPartDoc> swPartDoc;//获取零件
		swPartDoc = swDoc;

		swPartDoc->GetBodies2(swBodyType_e::swAllBodies, VARIANT_TRUE, &swBodyVT);//获取实体VT
		LPVOID bData = nullptr;
		LONG bCount;
		if (!ReadSafeArray(&swBodyVT, VT_DISPATCH, 1, &bData, &bCount)) {
			CoUninitialize();
			return false;
		}
		IDispatch** mybData = (IDispatch**)bData;
		IBody2* myBodyData;//用于获取IBody2*类型数据
		long bStartTime = GetTickCount();
		for (int bIndex = 0; bIndex < bCount; bIndex++) { //1294ms
			result = mybData[bIndex]->QueryInterface(IID_IBody2, (void**)&myBodyData);
			if (result != S_OK) {
				CoUninitialize();
				return false;
			}
			swBody = CComPtr<IBody2>(myBodyData);//得到实体

			//a.循环全部面
			CComPtr<IFace2> thisFace;//面
			CComPtr<IFace2> nextFace;//面
			swBody->IGetFirstFace(&thisFace);

			while (thisFace)
			{
				//b.选择无标注的面
				swEntity = thisFace;
				CComBSTR faceName;
				result = swEntity->get_ModelName(&faceName);//查看面的模型名称
				if (faceName == "") { //名称为空说明该面没有读取过特征标注
					VARIANT_BOOL isSelected;
					result = swEntity->Select4(VARIANT_TRUE, nullptr, &isSelected);
					hasNoMBDFace = true;
				}
				else {
					VARIANT_BOOL isDeSelected;
					result = swEntity->DeSelect(&isDeSelected);
				}
				nextFace.Release();
				result = thisFace->IGetNextFace(&nextFace);
				thisFace = nextFace;
			}


		}
		long bEndTime = GetTickCount();
		bTime = bEndTime - bStartTime;
		//c.保存无MBD的面
		if (hasNoMBDFace) {
			CComBSTR noMBDFaceName = "0_NoMBDFace";
			MyFaceFeature noMBDFace;
			noMBDFace.AnnotationCount = 0;
			noMBDFace.Name = "0_NoMBDFace";
			//noMBDFace.AppliedFaceNameBSTR = noMBDFaceName;
			MyAnnotation noMBDAnnotation;
			noMBDAnnotation.Name = "NoMBD";
			noMBDFace.AnnotationArray.push_back(noMBDAnnotation);
			FaceMap["0_NoMBDFace"] = noMBDFace;

			long error = NOERROR;
			long warning = NOERROR;
			VARIANT_BOOL isSaved;
			CComBSTR savePath = (CADPath + CADName + "\\" + "0_NoMBDFace.STL").c_str();
			result = swDoc->SaveAs4(savePath, swSaveAsCurrentVersion, swSaveAsOptions_Silent, &error, &warning, &isSaved);//保存文件
			if (result != S_OK) {
				CoUninitialize();
				return false;
			}
		}
		

		//获取建模的特征（非DimXpert）
		//result = swDoc->get_FeatureManager(&swFeatureManager);
		//if (result != S_OK) {
		//	CoUninitialize();
		//	return false;
		//}
		//result = swFeatureManager->get_FeatureStatistics(&swFeatureStatistics);
		//if (result != S_OK) {
		//	CoUninitialize();
		//	return false;
		//}
		//VARIANT_BOOL temp1 = VARIANT_FALSE;
		//swFeatureStatistics->Refresh(&temp1);
		//
		//result = swFeatureStatistics->get_FeatureCount(&featureCount);
		//if (result != S_OK) {
		//	CoUninitialize();
		//	return false;
		//}
		//result = swFeatureStatistics->get_FeatureNames(&featureNames);
		//// verify that it's an array
		//if (V_ISARRAY(&featureNames))
		//{
		//	// get safe array
		//	LPSAFEARRAY pSafeArray = V_ARRAY(&featureNames);
		//
		//	// determine the type of item in the array
		//	VARTYPE itemType;
		//	if (SUCCEEDED(SafeArrayGetVartype(pSafeArray, &itemType)))
		//	{
		//		// verify it's the type you expect
		//		// (The API you're using probably returns a safearray of VARIANTs,
		//		// so I'll use VT_VARIANT here. You should double-check this.)
		//		if (itemType == VT_BSTR)//////////////////////////////////////////////////////////////////////
		//		{
		//			// verify that it's a one-dimensional array
		//			// (The API you're using probably returns a one-dimensional array.)
		//			if (SafeArrayGetDim(pSafeArray) == 1)
		//			{
		//				// determine the upper and lower bounds of the first dimension
		//				LONG lBound;
		//				LONG uBound;
		//				if (SUCCEEDED(SafeArrayGetLBound(pSafeArray, 1, &lBound)) && SUCCEEDED(SafeArrayGetUBound(pSafeArray, 1, &uBound)))
		//				{
		//					// determine the number of items in the array
		//					LONG itemCount = uBound - lBound + 1;
		//
		//					// begin accessing data
		//					LPVOID pData;
		//					if (SUCCEEDED(SafeArrayAccessData(pSafeArray, &pData)))
		//					{
		//						// here you can cast pData to an array (pointer) of the type you expect
		//						// (The API you're using probably returns a safearray of VARIANTs,
		//						// so I'll use VARIANT here. You should double-check this.)
		//						BSTR* sgg = (BSTR*)pData;////////////////////////////////////////////////////////////////////////
		//
		//						// use the data here.
		//						for (int i = 0; i++; i < 8) {
		//							s[i] = GbkToUtf8(_com_util::ConvertBSTRToString(sgg[i]));
		//						}
		//
		//						// end accessing data
		//						SafeArrayUnaccessData(pSafeArray);
		//					}
		//				}
		//			}
		//		}
		//	}
		//}

		
		DimXpertFeatureCount = FaceMap.size();//获取DimXpert特征数量

		long allEndTime = GetTickCount();
		allTime = allEndTime - allStartTime;

		return true;
	}

	


	bool MyApplication::LoadModel()
	{
		return true;
	}

	bool MyApplication::ReadMassProperty()
	{
		swDispatch.Release();
		result = swDocE->CreateMassProperty2(&swDispatch);
		swMassProperty = swDispatch;
		result = swMassProperty->get_CenterOfMass(&massCenterVT);

		LPVOID mcData = nullptr;
		LONG mcCount;
		if (!ReadSafeArray(&massCenterVT, VT_R8, 1, &mcData, &mcCount)) {
			CoUninitialize();
			return false;
		}
		double* mymcData = (double*)mcData;
		MassCenter = glm::vec3(mymcData[0], mymcData[1], mymcData[2]) * 1000.0f; //米->毫米

		return true;
	}

	std::string  MyApplication::GbkToUtf8(const char* src_str)
	{
		int len = MultiByteToWideChar(CP_ACP, 0, src_str, -1, NULL, 0);
		wchar_t* wstr = new wchar_t[len + 1];
		memset(wstr, 0, len + 1);
		MultiByteToWideChar(CP_ACP, 0, src_str, -1, wstr, len);
		len = WideCharToMultiByte(CP_UTF8, 0, wstr, -1, NULL, 0, NULL, NULL);
		char* str = new char[len + 1];
		memset(str, 0, len + 1);
		WideCharToMultiByte(CP_UTF8, 0, wstr, -1, str, len, NULL, NULL);
		std::string strTemp = str;
		if (wstr) delete[] wstr;
		if (str) delete[] str;
		return strTemp;
	}


	bool MyApplication::ReadSafeArray(VARIANT* vt,VARENUM vtType,int dimensional,LPVOID* pData, LONG* itemCount)
	{
		//读取SAFEARRAY
		// verify that it's an array
		if (V_ISARRAY(vt))
		{
			// get safe array
			SAFEARRAY* pSafeArray = V_ARRAY(vt);
			// determine the type of item in the array
			VARTYPE itemType;
			if (SUCCEEDED(SafeArrayGetVartype(pSafeArray, &itemType)))
			{
				// verify it's the type you expect
				if (itemType == vtType)///////////////////////该数组类型为存储IDispatch*指针的数组
				{
					// verify that it's a one-dimensional array
					if (SafeArrayGetDim(pSafeArray) == dimensional)
					{
						// determine the upper and lower bounds of the first dimension
						LONG lBound;
						LONG uBound;
						if (SUCCEEDED(SafeArrayGetLBound(pSafeArray, 1, &lBound)) && SUCCEEDED(SafeArrayGetUBound(pSafeArray, 1, &uBound)))
						{
							// determine the number of items in the array
							*itemCount = uBound - lBound + 1;
							// begin accessing data
							//LPVOID pData;
							if (SUCCEEDED(SafeArrayAccessData(pSafeArray, &*pData)))//提取数组指针至pData
							{
								// end accessing data
								SafeArrayUnaccessData(pSafeArray);
								return true;
							}
							else {
								CoUninitialize();
								return false;
							}
						}
						else {
							CoUninitialize();
							return false;
						}
					}
				}
			}
			else {
				CoUninitialize();
				return false;
			}
		}
	}

	template<typename T>
	bool MyApplication::CreatVARIANTArray(int size, VARENUM type, T* buffer, VARIANT* array)
	{
		SAFEARRAY* psa; //使用数组整理读取的数据
		SAFEARRAYBOUND rgsabound[1];
		rgsabound[0].cElements = size; //设置数组的大小
		rgsabound[0].lLbound = 0;
		psa = SafeArrayCreate(type, 1, rgsabound); //创建SafeArray数组

		long len = psa->rgsabound[0].cElements;
		for (long i = 0; i < len; i++) {
			result = SafeArrayPutElement(psa, &i, &buffer[i]);
			if (result != S_OK) {
				CoUninitialize();
				return false;
			}
		}
		array->vt = VT_ARRAY | VT_R8; //数组类型
		array->parray = psa;
		return true;
	}

	double MyApplication::ReadDoubleFromString(std::string textstr)
	{
		std::regex pattern("\\d+[.]\\d");	//1开头，后面[3578]中的一个，九个数字
		std::string::const_iterator iter_begin = textstr.cbegin();
		std::string::const_iterator iter_end = textstr.cend();
		std::smatch matchResult;
		if (std::regex_search(iter_begin, iter_end, matchResult, pattern)) {
			return std::stod(matchResult[0]);
		}
		else {
			return 666;
		}
	}

	void MyApplication::ReadAnnotationData(swDimXpertAnnotationType_e annoType, double* toleranceSize, int* toleranceLevel, std::string* myDatumName, std::vector<std::string>& datumNames, swDimXpertMaterialConditionModifier_e* MCMType)
	{
		if (annoType == swDimXpertAnnotationType_e::swDimXpertDatum) {
			DatumData(myDatumName);
		}
		else if (GeoTolMap[annoType]>0) {
			GeoTolData(annoType, toleranceSize, toleranceLevel, datumNames, MCMType);
		}
		else if (DimTolMap[annoType]>0) {
			DimTolData(annoType, toleranceSize, toleranceLevel);
		}
		else {
			//类型为unknown
		}
		
	}

	void MyApplication::DatumData(std::string* datumName)
	{
		CComPtr<IDimXpertDatum> datum;
		datum = swDimXpertAnnotation;
		CComBSTR identifier;
		result = datum->get_Identifier(&identifier);//A\B\C
		*datumName = GbkToUtf8(_com_util::ConvertBSTRToString(identifier));
		
	}

	void MyApplication::GeoTolData(swDimXpertAnnotationType_e annoType, double* toleranceSize, int* toleranceLevel, std::vector<std::string>& datumNames, swDimXpertMaterialConditionModifier_e* MCMType)
	{
		CComPtr<IDimXpertTolerance> tolerance;
		tolerance = swDimXpertAnnotation;
		result = tolerance->get_Tolerance(toleranceSize);//(平性)0.05(垂直度)0.1(定位1)0.2
		*toleranceLevel = 1;//需用国标判断,需要知道面的尺寸才能知道公差等级

		long primaryCount;
		long secondaryCount;
		long tertiaryCount;
		CComPtr<IDimXpertDatum> datum;
		CComBSTR identifier;
		result = tolerance->GetPrimaryDatumCount(&primaryCount);
		if(primaryCount >0) {
			datum.Release();
			result = tolerance->IGetPrimaryDatums(primaryCount, &datum);			
			result = datum->get_Identifier(&identifier);//A
			datumNames.push_back(GbkToUtf8(_com_util::ConvertBSTRToString(identifier)));
		}
		result = tolerance->GetSecondaryDatumCount(&secondaryCount);
		if (secondaryCount > 0) {
			datum.Release();
			result = tolerance->IGetSecondaryDatums(secondaryCount, &datum);
			result = datum->get_Identifier(&identifier);//A
			datumNames.push_back(GbkToUtf8(_com_util::ConvertBSTRToString(identifier)));
		}
		result = tolerance->GetTertiaryDatumCount(&tertiaryCount);
		if (tertiaryCount > 0) {
			datum.Release();
			result = tolerance->IGetTertiaryDatums(tertiaryCount, &datum);
			result = datum->get_Identifier(&identifier);//A
			datumNames.push_back(GbkToUtf8(_com_util::ConvertBSTRToString(identifier)));
		}
		if (GeoTolMap[annoType] > 1) {
			CComPtr<IDimXpertPositionTolerance> tol1;
			CComPtr<IDimXpertCompositePositionTolerance> tol2;
			CComPtr<IDimXpertSymmetryTolerance> tol3;
			CComPtr<IDimXpertConcentricityTolerance> tol4;
			CComPtr<IDimXpertStraightnessTolerance> tol5;
			CComPtr<IDimXpertOrientationTolerance> tol678;
			switch (annoType)
			{
			case swDimXpertGeoTol_Position:
				tol1 = swDimXpertAnnotation;
				result = tol1->get_Modifier(MCMType);
				break;
			case swDimXpertGeoTol_CompositePosition:
				tol2 = swDimXpertAnnotation;
				result = tol2->get_Modifier(MCMType);
				break;
			case swDimXpertGeoTol_Symmetry:
				tol3 = swDimXpertAnnotation;
				result = tol3->get_Modifier(MCMType);
				break;
			case swDimXpertGeoTol_Concentricity:
				tol4 = swDimXpertAnnotation;
				result = tol4->get_Modifier(MCMType);
				break;
			case swDimXpertGeoTol_Straightness:
				tol5 = swDimXpertAnnotation;
				result = tol5->get_Modifier(MCMType);
				break;
			default:
				tol678 = swDimXpertAnnotation;
				result = tol678->get_Modifier(MCMType);
				break;
			}

		}
		
		
	}

	void MyApplication::DimTolData(swDimXpertAnnotationType_e annoType, double* toleranceSize, int* toleranceLevel)
	{
		CComPtr<IDimXpertDimensionTolerance> dimensionTolerance;
		dimensionTolerance = swDimXpertAnnotation;

		double upper = 0;
		double lower = 0;
		VARIANT_BOOL boolstatus = VARIANT_FALSE;

		bool isAngleType = false;
		isAngleType = annoType == swDimXpertAnnotationType_e::swDimXpertDimTol_ConeAngle ? true : false;

		double dbl = 0;
		dbl = isAngleType ? 57.2957795130823 : 1.0;// conversion for radians to degrees when dimension type is angle

		// the nominal, and upper and lower limits of size of the dimension
		double nominalValue = 0;
		result = dimensionTolerance->GetNominalValue(&nominalValue);//名义值,(之间距离1)30 (直径1)10
		nominalValue *= dbl;

		result = dimensionTolerance->GetUpperAndLowerLimit(&upper, &lower, &boolstatus);//(之间距离1)30.5 29.5 (直径1)10.25 9.75
		upper *= dbl;
		lower *= dbl;

		//if(annoType == )
		*toleranceSize = upper - lower;
		*toleranceLevel = 1;//需用国标判断，需要区分轴/孔和基本尺寸，还需知道面尺寸
	}

	
		
	
	/*
	void MyApplication::FeatureLoop(int feIndex, IDispatch**& myfeData)
	{		
		//mtx.lock();
		IDimXpertFeature* myFeatureData;//用于最终获取IDimXpertFeature*类型数据		
		CComBSTR dimXpertFeatureName;
		CComBSTR dimXpertAnnotationName;
		std::string dimXpertFeatureNameStr;
		std::string dimXpertAnnotationNameStr;
		CComPtr<IDimXpertFeature> swDimXpertFeature;//DimXpert特征

		result = myfeData[feIndex]->QueryInterface(IID_IDimXpertFeature, (void**)&myFeatureData);
		swDimXpertFeature = CComPtr<IDimXpertFeature>(myFeatureData);//用构造函数将IDimXpertFeature*普通指针转为CComPtr智能指针					
		//a.获取特征名称
		result = swDimXpertFeature->get_Name(&dimXpertFeatureName);//result为false？不知为何，但是能读取
		//if (result != S_OK) {
		//	CoUninitialize();										
		//	return false;
		//}
		dimXpertFeatureNameStr = GbkToUtf8(_com_util::ConvertBSTRToString(dimXpertFeatureName));//BSTR转String(Gbk)(Imgui会乱码)，再转String(Utf8)			

		//存入特征面数组
		MyFaceFeature faceFeature;
		faceFeature.Name = dimXpertFeatureNameStr;

		//2.获取标注SAFEARRAY数组的承载体
		result = swDimXpertFeature->GetAppliedAnnotations(&dimXpertAnnotationVT);
		//读取DimXpert标注的SAFEARRAY
		LPVOID aData = nullptr;//接收读取后的数组
		LONG annotationCount;//接收读取后的数组大小
		bool ToContinue = false;
		if (!ReadSafeArray(&dimXpertAnnotationVT, VT_DISPATCH, 1, &aData, &annotationCount)) {
			ToContinue = true;
		}
		if (aData == nullptr) {
			ToContinue = true;//Realease模式下ReadSafeArray判断一直失误，不明原因
		}
		if(!ToContinue)
		{
			faceFeature.AnnotationCount = annotationCount;
			IDispatch** myaData = (IDispatch**)aData;//将数组指针赋与IDispatch**类型的指针数组的指针，与ReadSafeArray类型一致
			IDimXpertAnnotation* myAnnotationData;//用于获取IDimXpertAnnotation*类型数据
			long aStartTime = GetTickCount();
			for (int aIndex = 0; aIndex < annotationCount; aIndex++) { //243ms
				result = myaData[aIndex]->QueryInterface(IID_IDimXpertAnnotation, (void**)&myAnnotationData);//为了将IDispatch*类型转为IDimXpertAnnotation*，需要用QueryInterface查询是否可转换(CComPtr类型直接=即可)，IID_IDimXpertAnnotation是要查询的接口类型
				swDimXpertAnnotation = CComPtr<IDimXpertAnnotation>(myAnnotationData);//用构造函数将IDimXpertAnnotation*普通指针转为CComPtr智能指针

				//a.获取标注名称
				result = swDimXpertAnnotation->get_Name(&dimXpertAnnotationName);
				//if (result != S_OK) {
				//	CoUninitialize();										
				//	return false;
				//}
				dimXpertAnnotationNameStr = GbkToUtf8(_com_util::ConvertBSTRToString(dimXpertAnnotationName));

				//b.获取标注类型
				swDimXpertAnnotationType_e dimXpertAnnotationType;
				result = swDimXpertAnnotation->get_Type(&dimXpertAnnotationType);

				//c.获取公差
				double toleranceSize = 0;
				int toleranceLevel = 0;
				std::string datumName;
				std::vector<std::string> toleranceDatumNames;
				swDimXpertMaterialConditionModifier_e MCMType = swDimXpertMaterialConditionModifier_unknown;
				ReadAnnotationData(dimXpertAnnotationType, &toleranceSize, &toleranceLevel, &datumName, toleranceDatumNames, &MCMType);//可以返回公差等级（1.轴/孔 2.线性尺寸 3.形位公差 三者等级定义不同）

				//存入特征面数组的标注数组
				MyAnnotation myAnnotation;
				myAnnotation.Name = dimXpertAnnotationNameStr;
				myAnnotation.Type = dimXpertAnnotationType;
				myAnnotation.IsTolerance = dimXpertAnnotationType != swDimXpertDatum ? 1 : 0;
				myAnnotation.AccuracySize = toleranceSize;
				myAnnotation.AccuracyLevel = toleranceLevel;
				myAnnotation.IsDatum = dimXpertAnnotationType == swDimXpertDatum ? 1 : 0;
				myAnnotation.DatumName = datumName;
				myAnnotation.ToleranceDatumNames = toleranceDatumNames;
				myAnnotation.hasMCM = MCMType != swDimXpertMaterialConditionModifier_unknown ? 1 : 0;
				myAnnotation.MCMType = MCMType;
				faceFeature.AnnotationArray.push_back(myAnnotation);

			}
			long aEndTime = GetTickCount();
			//aTime += ((aEndTime - aStartTime) / annotationCount);

			
			//3.读取DimXpert特征所对应的面并保存为文件

			//a.设定当前面的名称
			CComBSTR faceName = "";
			std::string fileIndex = std::to_string(feIndex);//int转string
			result = faceName.Append(fileIndex.c_str());
			result = faceName.Append("_");
			result = faceName.Append(dimXpertFeatureName);

			//b.读取DimXpert特征所对应的面
			result = swDimXpertFeature->GetFaces(&faceVT);
			//读取面的SAFEARRAY
			LPVOID fData = nullptr;
			LONG faceCount;
			if (!ReadSafeArray(&faceVT, VT_DISPATCH, 1, &fData, &faceCount)) {
				
			}
			IDispatch** myfData = (IDispatch**)fData;
			IFace2* myFaceData;//用于获取IFace2*类型数据			
			long fStartTime = GetTickCount();
			for (int fIndex = 0; fIndex < faceCount; fIndex++) { //15ms
				result = myfData[fIndex]->QueryInterface(IID_IFace2, (void**)&myFaceData);
				swFace = CComPtr<IFace2>(myFaceData);
				swEntity = swFace;
				swEntity->put_ModelName(faceName);//设置模型名

				//b.使SW自动选择当前特征对应的面
				VARIANT_BOOL isSelected;
				if (fIndex > 0) {
					swEntity->Select4(VARIANT_TRUE, nullptr, &isSelected);
				}
				else {
					swEntity->Select4(VARIANT_FALSE, nullptr, &isSelected);
				}







				//在包围盒范围内向面投影光线 求交点，100个点需要20多秒，太慢了
				//myFaceData->GetBox(&boxVT);//获取包围盒坐标。一共6个值：第一个点的xyz，第二个点的xyz，单位m
				////读取包围盒的SAFEARRAY
				//LPVOID bData = nullptr;
				//LONG boxCount;
				//if (!ReadSafeArray(&boxVT, VT_R8, 1, &bData, &boxCount)) {
				//	CoUninitialize();
				//	return false;
				//}
				//// here you can cast pData to an array (pointer) of the type you expect
				//double* mybData = (double*)bData;
				//// use the data here.
				//double myBoxPos1[3] = { 0,0,0 };//用于获取double类型数据	
				//double myBoxPos2[3] = { 0,0,0 };//用于获取double类型数据	
				//for (int i = 0; i < boxCount; i++) {
				//	if (i < 3)
				//		myBoxPos1[i] = mybData[i];//包围盒点1
				//	else
				//		myBoxPos2[i - 3] = mybData[i];//包围盒点2
				//}
				//
				//double thisPos[3];//目前的投影光线起点
				//double dir[3] = { 1,0,0 };//目前的投影光线方向
				//int sampleCount = 10;//投影采样次数
				//for (int i = 0; i < sampleCount; i++) {
				//	thisPos[0] = myBoxPos1[0] + i * (myBoxPos2[0] - myBoxPos1[0]) / sampleCount;
				//	thisPos[1] = myBoxPos1[1] + i * (myBoxPos2[1] - myBoxPos1[1]) / sampleCount;
				//	thisPos[2] = myBoxPos1[2] + i * (myBoxPos2[2] - myBoxPos1[2]) / sampleCount;
				//
				//	startPoint.Release();
				//	projectDir.Release();
				//	interactPoint.Release();
				//
				//	CreatVARIANTArray(3, VT_R8, thisPos, &startPointVT);//生成VARIANT数组
				//	swDispatch.Release();
				//	result = swMathUtility->CreatePoint(startPointVT, &swDispatch);//生成点
				//	startPoint = swDispatch;
				//
				//	CreatVARIANTArray(3, VT_R8, dir, &projectDirVT);//生成VARIANT数组
				//	swDispatch.Release();
				//	result = swMathUtility->CreateVector(projectDirVT, &swDispatch);//生成向量
				//	projectDir = swDispatch;
				//
				//	result = swFace->GetProjectedPointOn(startPoint, projectDir, &interactPoint);//投影，求得的交点单位是m，若未相交为NULL
				//	if (interactPoint != NULL) {
				//		result = interactPoint->get_ArrayData(&interactPointVT);
				//		LPVOID iData = nullptr;
				//		LONG iCount;
				//		if (ReadSafeArray(&interactPointVT, VT_R8, 1, &iData, &iCount)) {
				//			//存数据
				//		}
				//
				//	}
				//
				//}






			}
			long fEndTime = GetTickCount();
			//fTime += ((fEndTime - fStartTime) / faceCount);

			//c.以面命名将特征存入面哈希表							
			//VARIANT_BOOL isSetName = VARIANT_FALSE;
			//swDoc->SelectedFaceProperties(0, 0, 0, 0, 0, 0, 0, VARIANT_TRUE, faceName,&isSetName);//设置面属性的名字（sw右键面属性可见）
			std::string FaceName = GbkToUtf8(_com_util::ConvertBSTRToString(faceName));
			FaceMap[FaceName] = faceFeature;
			//FaceMap[FaceName].AppliedFaceNameBSTR = faceName.Copy();//给特征存储所属面的BSTR名(因为string转回BSTR有乱码)

			//d.保存面为stl文件（当有选中的面时，直接保存时默认保存该面）
			if (toSave) {
				long error = NOERROR;
				long warning = NOERROR;
				VARIANT_BOOL isSaved;
				result = faceName.Append(".STL");
				CComBSTR savePath = (CADPath + CADName + "\\").c_str();
				result = savePath.Append(faceName);
				result = swApp->SetUserPreferenceToggle(swUserPreferenceToggle_e::swSTLDontTranslateToPositive, VARIANT_TRUE);//设置sw导出stl时不正向化坐标系（保留建模的坐标系）
				result = swDoc->SaveAs4(savePath, swSaveAsCurrentVersion, swSaveAsOptions_Silent, &error, &warning, &isSaved);//保存文件
			}
		}


		//mtx.unlock();
		
	}

	void MyApplication::AnnotationLoop(int aIndex, IDispatch**& myaData, MyFaceFeature& faceFeature)
	{
		CComBSTR dimXpertAnnotationName;
		std::string dimXpertAnnotationNameStr;
		IDimXpertAnnotation* myAnnotationData;//用于获取IDimXpertAnnotation*类型数据
		result = myaData[aIndex]->QueryInterface(IID_IDimXpertAnnotation, (void**)&myAnnotationData);//为了将IDispatch*类型转为IDimXpertAnnotation*，需要用QueryInterface查询是否可转换(CComPtr类型直接=即可)，IID_IDimXpertAnnotation是要查询的接口类型
		swDimXpertAnnotation = CComPtr<IDimXpertAnnotation>(myAnnotationData);//用构造函数将IDimXpertAnnotation*普通指针转为CComPtr智能指针

		//a.获取标注名称
		result = swDimXpertAnnotation->get_Name(&dimXpertAnnotationName);
		//if (result != S_OK) {
		//	CoUninitialize();										
		//	return false;
		//}
		dimXpertAnnotationNameStr = GbkToUtf8(_com_util::ConvertBSTRToString(dimXpertAnnotationName));

		//b.获取标注类型
		swDimXpertAnnotationType_e dimXpertAnnotationType;
		result = swDimXpertAnnotation->get_Type(&dimXpertAnnotationType);

		//c.获取公差
		double toleranceSize = 0;
		int toleranceLevel = 0;
		std::string datumName;
		std::vector<std::string> toleranceDatumNames;
		swDimXpertMaterialConditionModifier_e MCMType = swDimXpertMaterialConditionModifier_unknown;
		ReadAnnotationData(dimXpertAnnotationType, &toleranceSize, &toleranceLevel, &datumName, toleranceDatumNames, &MCMType);//可以返回公差等级（1.轴/孔 2.线性尺寸 3.形位公差 三者等级定义不同）

		//存入特征面数组的标注数组
		
		MyAnnotation myAnnotation;
		myAnnotation.Name = dimXpertAnnotationNameStr;
		myAnnotation.Type = dimXpertAnnotationType;
		myAnnotation.IsTolerance = dimXpertAnnotationType != swDimXpertDatum ? 1 : 0;
		myAnnotation.AccuracySize = toleranceSize;
		myAnnotation.AccuracyLevel = toleranceLevel;
		myAnnotation.IsDatum = dimXpertAnnotationType == swDimXpertDatum ? 1 : 0;
		myAnnotation.DatumName = datumName;
		myAnnotation.ToleranceDatumNames = toleranceDatumNames;
		myAnnotation.hasMCM = MCMType != swDimXpertMaterialConditionModifier_unknown ? 1 : 0;
		myAnnotation.MCMType = MCMType;
		mtx.lock();
		faceFeature.AnnotationArray.push_back(myAnnotation);
		mtx.unlock();
	}
	*/
}

